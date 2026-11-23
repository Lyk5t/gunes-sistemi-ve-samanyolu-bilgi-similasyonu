"""Sahne katmanı: gezegenlerin 3B nesnelerini kurar ve hareket ettirir.
Yüzey haritaları dokular.py içinde üretilir."""
import math
import random
import time

from PIL import Image
from ursina import Entity, Mesh, Shader, Sky, Texture, Vec3, destroy
from ursina.color import Color

import dokular
from dokular import hex_rgb

try:   # eksen eğikliği için (panda3d, ursina ile birlikte gelir)
    from panda3d.core import Quat
    from panda3d.core import Vec3 as PVec3
except ImportError:
    Quat = None

# ---- grafik ayarları: bir şey bozuk görünürse ilgili ayarı False yapın ----
GOLGELEME = True         # Güneş ışığı (gündüz/gece). False: düz renkli gezegenler
GELISMIS = True          # kabartma, okyanus parlaması, şehir ışıkları, bulut katmanı, halka gölgesi
ATMOSFER_PARLAMA = True  # gezegen kenarında dışa taşan atmosfer ışıması
UZAY_ARKAPLANI = True    # Samanyolu arka planı
GUNES_GOLGELENDIRICI = True  # Güneş: hareketli yüzey, lekeler, kenar kararması
GAZ_AKISI = True         # gaz devlerinde yavaşça kıvrılan bulut bantları

# Canlı veri satırları: (başlık, sözlük anahtarı, birim, en küçük sapma, grafik rengi)
CANLI = [
    ("Sıcaklık", "sicak", "°C", 0.8, "#ff9a4d"),
    ("Basınç", "basinc", "bar", 0.0, "#4de1d2"),
    ("Rüzgâr hızı", "ruzgar", "m/s", 0.5, "#b79bff"),
]

# Gerçek gökbilim verileri (gezegen modüllerinde yoksa buradan okunur).
#   egim: dönme ekseni eğikliği (derece), donme: kendi etrafında dönme süresi (saat)
#   aylar: (ad, yarıçap km, uzaklık [gezegen yarıçapı], periyot gün, renk)
EK = {
    "Merkür": dict(egim=0.03, donme=1407.6),
    "Venüs": dict(egim=177.4, donme=5832.5),
    "Dünya": dict(egim=23.4, donme=23.9, aylar=[("Ay", 1737, 4.0, 27.3, "#b8b5ae")]),
    "Mars": dict(egim=25.2, donme=24.6),
    "Jüpiter": dict(egim=3.1, donme=9.9, aylar=[
        ("Io", 1822, 2.6, 1.77, "#e8d27a"), ("Europa", 1561, 3.2, 3.55, "#d8cfc0"),
        ("Ganymede", 2634, 4.0, 7.15, "#9b8f80"), ("Callisto", 2410, 4.9, 16.7, "#6e6459")]),
    "Satürn": dict(egim=26.7, donme=10.7, aylar=[("Titan", 2575, 4.2, 15.9, "#d9a64f")]),
    "Uranüs": dict(egim=97.8, donme=17.2),
    "Neptün": dict(egim=28.3, donme=16.1),
}


def ozellik(v, anahtar, varsayilan):
    if anahtar in v:
        return v[anahtar]
    return EK.get(v["ad"], {}).get(anahtar, varsayilan)


# =====================================================================
#  GÖLGELENDİRİCİLER (GLSL 1.40)
# =====================================================================
GIRIS = """#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec3 wn;
out vec3 wp;
out vec3 vn;
out vec3 vv;
out vec3 op;
out vec3 pc;
"""
# Küre için ortak köşe gölgelendirici (atmosfer, bulut, Güneş)
VS_KURE = GIRIS + """
void main() {
    vec3 n = normalize(p3d_Vertex.xyz);
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    wp = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wn = mat3(p3d_ModelMatrix) * n;
    vn = mat3(p3d_ModelViewMatrix) * n;
    vv = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
    op = n;
    pc = p3d_ModelMatrix[3].xyz;
}"""

# Gelişmiş gezegen: kabartma için teğet çerçevesi de üretir
VS_GEZEGEN = GIRIS + """
out vec3 wt;
out vec3 wb;
void main() {
    vec3 n = normalize(p3d_Vertex.xyz);
    vec3 t = cross(vec3(0.0, 0.0, 1.0), n);
    if (length(t) < 0.0001) t = vec3(1.0, 0.0, 0.0);
    t = normalize(t);
    vec3 b = cross(n, t);
    mat3 m = mat3(p3d_ModelMatrix);
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    wp = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wn = m * n;
    wt = m * t;
    wb = m * b;
    vn = mat3(p3d_ModelViewMatrix) * n;
    vv = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
    op = n;
    pc = p3d_ModelMatrix[3].xyz;
}"""

# Gölgelendiricilerde ortak kullanılan 3B gürültü (GPU'da üretilir, doku gerektirmez)
GURULTU = """
float hsh(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float vnoise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    float a = mix(mix(hsh(i), hsh(i + vec3(1.0, 0.0, 0.0)), f.x),
                  mix(hsh(i + vec3(0.0, 1.0, 0.0)), hsh(i + vec3(1.0, 1.0, 0.0)), f.x), f.y);
    float b = mix(mix(hsh(i + vec3(0.0, 0.0, 1.0)), hsh(i + vec3(1.0, 0.0, 1.0)), f.x),
                  mix(hsh(i + vec3(0.0, 1.0, 1.0)), hsh(i + vec3(1.0, 1.0, 1.0)), f.x), f.y);
    return mix(a, b, f.z);
}
float fbm(vec3 p) {
    float a = 0.5;
    float s = 0.0;
    for (int i = 0; i < 4; i++) {
        s += a * vnoise(p);
        p = p * 2.03 + vec3(1.7, 9.2, 3.1);
        a *= 0.5;
    }
    return s;
}
"""

FS_GEZEGEN = """#version 140
uniform sampler2D p3d_Texture0;
uniform sampler2D normal_map;
uniform sampler2D ozel_map;
uniform sampler2D bulut_map;
uniform sampler2D halka_map;
uniform mat4 p3d_ViewMatrix;
uniform vec3 atm_renk;
uniform vec3 halka_n;
uniform float atm_k;
uniform float bump;
uniform float zaman;
uniform float gaz;
uniform float bulut_ofs;
uniform float pr;
uniform float halka_var;
uniform float halka_ic;
uniform float halka_dis;
in vec2 uv;
in vec3 wn;
in vec3 wp;
in vec3 vn;
in vec3 vv;
in vec3 wt;
in vec3 wb;
in vec3 op;
in vec3 pc;
out vec4 fragColor;
""" + GURULTU + """
// Halkanın gezegen yüzeyine düşürdüğü gölge (Güneş yönünde ışın izleme)
float halka_golge(vec3 L) {
    float dn = dot(L, halka_n);
    float t = dot(pc - wp, halka_n) / (abs(dn) < 0.001 ? 0.001 : dn);
    vec3 h = wp + L * t;
    float u = (length(h - pc) - halka_ic) / max(halka_dis - halka_ic, 0.0001);
    float a = textureLod(halka_map, vec2(clamp(u, 0.0, 1.0), 0.5), 0.0).a;
    float gecerli = (halka_var > 0.5 && t > 0.0 && u > 0.0 && u < 1.0) ? 1.0 : 0.0;
    return a * gecerli;
}
void main() {
    vec3 N0 = normalize(wn);
    vec3 L = normalize(-wp);                                   // Güneş (merkez) yönü
    float ndl0 = dot(N0, L);
    float px = length(fwidth(op));                             // 1 piksel = küre üzerinde ne kadar yol
    float a1 = 1.0 - smoothstep(0.004, 0.012, px);             // ince ayrıntı yalnızca yeterince yakınken
    float a2 = 1.0 - smoothstep(0.0013, 0.004, px);

    // gaz devleri: bulut bantları rüzgârla yavaşça kıvrılır
    vec2 uv2 = uv;
    if (gaz > 0.5) {
        vec3 q = op * 4.0 + vec3(zaman * 0.02, 0.0, 0.0);
        uv2 += (vec2(fbm(q), fbm(q + vec3(17.0, 5.0, 11.0))) - 0.5) * 0.018;
    }
    vec3 nm = texture(normal_map, uv2).xyz * 2.0 - 1.0;
    vec3 N = normalize(N0 + bump * (normalize(wt) * nm.x + normalize(wb) * nm.y));
    vec4 oz = texture(ozel_map, uv2);                          // r: okyanus, g: şehir ışıkları
    vec3 alb = pow(texture(p3d_Texture0, uv2).rgb, vec3(2.2));

    // yakından bakınca dokunun bulanıklığını örten ince yüzey ayrıntısı (kara/kaya yüzeyleri)
    if (gaz < 0.5) {
        float d = (fbm(op * 40.0) - 0.5) * a1 + (fbm(op * 130.0) - 0.5) * a2 * 0.8;
        alb *= 1.0 + d * 0.9 * (1.0 - oz.r);
        N = normalize(N + (vec3(fbm(op * 70.0 + 3.0), fbm(op * 70.0 + 7.0), fbm(op * 70.0 + 11.0)) - 0.5)
                         * 0.35 * bump * a1 * (1.0 - oz.r));
    }

    float gun = smoothstep(-0.08, 0.30, ndl0);                 // yumuşak gündüz/gece geçişi
    float diff = max(dot(N, L), 0.0) * gun;

    // gölgeler: halka ve (Dünya'da) bulutlar
    diff *= 1.0 - 0.9 * halka_golge(L);
    float bg = texture(bulut_map, vec2(uv.x - bulut_ofs, uv.y), 2.5).a;
    diff *= 1.0 - 0.22 * bg;

    vec3 Nv = normalize(mat3(p3d_ViewMatrix) * N);
    vec3 Lv = normalize(mat3(p3d_ViewMatrix) * L);
    vec3 Vv = normalize(-vv);
    float fres = pow(1.0 - max(dot(Nv, Vv), 0.0), 5.0);
    float spec = pow(max(dot(Nv, normalize(Lv + Vv)), 0.0), 90.0) * oz.r * gun * (1.0 - 0.8 * bg);
    spec *= 0.5 + 2.0 * fres;                                  // Fresnel: eğik bakışta yansıma artar

    // alacakaranlık: atmosferli gezegenlerde gün batımı kızıllığı
    float tw = smoothstep(-0.06, 0.04, ndl0) * (1.0 - smoothstep(0.04, 0.26, ndl0));
    float ak = clamp(atm_k, 0.0, 1.0);
    vec3 isik = mix(vec3(1.0), vec3(1.0, 0.62, 0.40), tw * ak * 0.55);

    vec3 lin = alb * (0.010 + 1.35 * diff) * isik;
    lin += vec3(1.0, 0.95, 0.85) * spec * 0.9;
    float gece = 1.0 - smoothstep(-0.14, 0.10, ndl0);
    lin += vec3(1.0, 0.72, 0.38) * oz.g * gece * (1.0 - bg) * 1.1;   // şehir ışıkları (bulut altında sönük)

    // atmosfer saçılması: kenarda mavi/turuncu ışıma
    float kenar = pow(1.0 - max(dot(normalize(vn), normalize(-vv)), 0.0), 3.0);
    vec3 sis = mix(atm_renk, vec3(1.0, 0.30, 0.08), tw * ak * 0.6);
    lin += sis * kenar * atm_k * smoothstep(-0.25, 0.55, ndl0) * 0.8;
    lin += atm_renk * ak * 0.05 * max(ndl0, 0.0);                // gündüz yüzeyinde ince hava perdesi

    vec3 x = lin * 0.72;                                       // pozlama + filmik ton eşleme (ACES)
    vec3 c = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
    fragColor = vec4(pow(c, vec3(1.0 / 2.2)), 1.0);
}"""

# Basit gezegen (GELISMIS = False)
FS_BASIT = """#version 140
uniform sampler2D p3d_Texture0;
uniform vec3 atm_renk;
uniform float atm_k;
in vec2 uv;
in vec3 wn;
in vec3 wp;
in vec3 vn;
in vec3 vv;
out vec4 fragColor;
void main() {
    float ndl = dot(normalize(wn), normalize(-wp));
    float gun = smoothstep(-0.10, 0.40, ndl);
    vec3 c = texture(p3d_Texture0, uv).rgb;
    vec3 renk = c * (0.03 + 1.08 * gun);
    float kenar = pow(1.0 - max(dot(normalize(vn), normalize(-vv)), 0.0), 3.0);
    renk += atm_renk * kenar * atm_k * smoothstep(-0.30, 0.50, ndl) * 1.5;
    fragColor = vec4(renk, 1.0);
}"""

# Atmosfer ışıması: gezegenden biraz büyük kürenin ARKA yüzleri, toplamalı karışımla çizilir
FS_ATM = """#version 140
uniform vec3 atm_renk;
uniform float atm_k;
uniform float atm_s;
in vec3 wn;
in vec3 wp;
in vec3 vn;
in vec3 vv;
out vec4 fragColor;
void main() {
    float d = abs(dot(normalize(vn), normalize(-vv)));
    float dl = sqrt(max(0.0001, 1.0 - 1.0 / (atm_s * atm_s)));
    float x = clamp(d / dl, 0.0, 1.0);
    float g = pow(x, 2.2) * 0.75 + pow(x, 6.0) * 0.5;          // geniş yumuşak hale + parlak iç kenar
    float sd = dot(normalize(wn), normalize(-wp));
    float isik = smoothstep(-0.35, 0.45, sd);
    float tw = smoothstep(-0.20, 0.0, sd) * (1.0 - smoothstep(0.05, 0.30, sd));
    vec3 renk = mix(atm_renk, vec3(1.0, 0.28, 0.07), tw * clamp(atm_k * 1.5, 0.0, 1.0) * 0.55);
    fragColor = vec4(renk * g * atm_k * isik * 1.7, 1.0);
}"""

# Bulut katmanı: dokunun alfa kanalı, Güneş'e göre aydınlanma; yüzeyden bağımsız kayar
FS_BULUT = """#version 140
uniform sampler2D p3d_Texture0;
uniform float bulut_ofs;
in vec2 uv;
in vec3 wn;
in vec3 wp;
out vec4 fragColor;
void main() {
    vec4 t = texture(p3d_Texture0, vec2(uv.x - bulut_ofs, uv.y));
    float ndl = dot(normalize(wn), normalize(-wp));
    float gun = smoothstep(-0.08, 0.35, ndl);
    float tw = smoothstep(-0.06, 0.04, ndl) * (1.0 - smoothstep(0.04, 0.26, ndl));
    vec3 lin = mix(vec3(1.0), vec3(1.0, 0.62, 0.42), tw * 0.2) * (0.012 + 1.35 * gun);
    vec3 x = lin * 0.72;
    vec3 c = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
    fragColor = vec4(pow(c, vec3(1.0 / 2.2)), t.a);
}"""

# Güneş: hareketli granülasyon, güneş lekeleri, kenar kararması
FS_GUNES = """#version 140
uniform sampler2D p3d_Texture0;
uniform float zaman;
in vec2 uv;
in vec3 vn;
in vec3 vv;
in vec3 op;
out vec4 fragColor;
""" + GURULTU + """
void main() {
    vec3 p = op * 6.0;
    float g1 = fbm(p * 2.0 + vec3(0.0, 0.0, zaman * 0.06));
    float g2 = fbm(p * 5.0 - vec3(zaman * 0.08, 0.0, 0.0));
    float gran = g1 * 0.65 + g2 * 0.35;
    vec3 doku = texture(p3d_Texture0, uv).rgb;
    float mu = max(dot(normalize(vn), normalize(-vv)), 0.0);
    float kenar = 0.30 + 0.70 * pow(mu, 0.55);                 // kenar kararması
    vec3 soguk = vec3(0.85, 0.22, 0.02);
    vec3 sicak = vec3(1.0, 0.93, 0.62);
    vec3 c = mix(soguk, sicak, smoothstep(0.30, 0.75, gran));
    c = mix(c, doku, 0.30);
    float leke = smoothstep(0.64, 0.72, fbm(op * 2.5 + 3.7));
    c *= 1.0 - 0.6 * leke;
    fragColor = vec4(c * kenar * 1.45, 1.0);
}"""

# Halka: gezegenin gölgesi halkanın üzerine düşer; Güneş'e karşı bakınca ışığı geçirir (ileri saçılma)
VS_HALKA = """#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
out vec3 wp;
out vec3 pc;
out vec3 vv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
    wp = (p3d_ModelMatrix * p3d_Vertex).xyz;
    pc = p3d_ModelMatrix[3].xyz;
    vv = (p3d_ModelViewMatrix * p3d_Vertex).xyz;
}"""
FS_HALKA = """#version 140
uniform sampler2D p3d_Texture0;
uniform mat4 p3d_ViewMatrix;
uniform float pr;
in vec2 uv;
in vec3 wp;
in vec3 pc;
in vec3 vv;
out vec4 fragColor;
void main() {
    vec4 t = texture(p3d_Texture0, uv);
    vec3 L = normalize(-pc);
    vec3 r = wp - pc;
    float along = dot(r, L);
    float golge = 0.0;
    if (along < 0.0) golge = 1.0 - smoothstep(pr * 0.94, pr * 1.04, length(r - L * along));
    vec3 Lv = normalize(mat3(p3d_ViewMatrix) * L);
    float ileri = pow(max(dot(normalize(vv), Lv), 0.0), 3.0);
    vec3 lin = pow(t.rgb, vec3(2.2)) * (0.06 + 1.35 * (1.0 - 0.92 * golge) * (1.0 + 1.6 * ileri * (1.0 - 0.5 * t.a)));
    vec3 x = lin * 0.72;
    vec3 c = clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
    fragColor = vec4(pow(c, vec3(1.0 / 2.2)), t.a * (1.0 - 0.25 * ileri));
}"""

KAYNAK = {
    "gezegen": (VS_GEZEGEN, FS_GEZEGEN), "basit": (VS_KURE, FS_BASIT), "atm": (VS_KURE, FS_ATM),
    "bulut": (VS_KURE, FS_BULUT), "halka": (VS_HALKA, FS_HALKA), "gunes": (VS_KURE, FS_GUNES),
}
_golgeler = {}


def golge(ad):
    if ad not in _golgeler:
        vs, fs = KAYNAK[ad]
        _golgeler[ad] = Shader(language=Shader.GLSL, vertex=vs, fragment=fs)
    return _golgeler[ad]


# =====================================================================
#  YARDIMCILAR
# =====================================================================
def hx(h, a=1.0, k=1.0):
    r, g, b = hex_rgb(h)
    return Color(min(1, r / 255 * k), min(1, g / 255 * k), min(1, b / 255 * k), a)


def dogrusal(h):
    r, g, b = hex_rgb(h)
    return Vec3((r / 255) ** 2.2, (g / 255) ** 2.2, (b / 255) ** 2.2)


def tex(img):
    """Mipmap + anizotropik süzme: uzaktan titreme olmaz, eğik bakışta keskin kalır."""
    t = Texture(img)
    try:
        t.filtering = "mipmap"
        t._texture.setAnisotropicDegree(8)
    except Exception:
        pass
    return t


_ortak = {}


def duz_dokular():
    if not _ortak:
        _ortak["normal"] = Texture(Image.new("RGB", (4, 4), (128, 128, 255)))
        _ortak["siyah"] = Texture(Image.new("RGB", (4, 4), (0, 0, 0)))
        _ortak["saydam"] = Texture(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    return _ortak["normal"], _ortak["siyah"]


def saydam_doku():
    duz_dokular()
    return _ortak["saydam"]


def girdi(e, ad, deger):
    if hasattr(deger, "_texture"):
        deger = deger._texture
    e.setShaderInput(ad, deger)


def kure(v, yaricap, atm_renk="#000000", atm_k=0.0, dok=None):
    """Gölgelendirilmiş küre (gezegen veya uydu)."""
    dok = dok or dokular.doku_uret(v, ayri_bulut=bool(GOLGELEME and GELISMIS))
    kw = {}
    if GOLGELEME:
        kw["shader"] = golge("gezegen" if GELISMIS else "basit")
    e = Entity(model="sphere", texture=tex(dok.renk), scale=yaricap * 2, **kw)
    if GOLGELEME:
        girdi(e, "atm_renk", dogrusal(atm_renk) if GELISMIS else Vec3(*[c / 255 for c in hex_rgb(atm_renk)]))
        girdi(e, "atm_k", float(atm_k))
        if GELISMIS:
            duz_n, siyah = duz_dokular()
            girdi(e, "normal_map", tex(dok.normal) if dok.normal is not None else duz_n)
            girdi(e, "ozel_map", tex(dok.ozel) if dok.ozel is not None else siyah)
            girdi(e, "bump", float(dok.bump))
            girdi(e, "zaman", 0.0)
            girdi(e, "gaz", 1.0 if ((v.get("doku") or "gaz") == "gaz" and GAZ_AKISI) else 0.0)
            girdi(e, "bulut_ofs", 0.0)
            girdi(e, "pr", float(yaricap))
            girdi(e, "halka_var", 0.0)
            girdi(e, "halka_ic", 1.0)
            girdi(e, "halka_dis", 2.0)
            girdi(e, "halka_n", Vec3(0, 0, 1))
            girdi(e, "halka_map", saydam_doku())
            e.bulut_tex = tex(dok.bulut) if dok.bulut is not None else None
            girdi(e, "bulut_map", e.bulut_tex if e.bulut_tex is not None else saydam_doku())
    e.dok = dok
    return e


def halka_mesh(ic, dis, n=120):
    v, t, uv = [], [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        v += [Vec3(math.cos(a) * ic, 0, math.sin(a) * ic), Vec3(math.cos(a) * dis, 0, math.sin(a) * dis)]
        uv += [(0, .5), (1, .5)]
    for i in range(n):
        a, b = i * 2, (i * 2 + 2) % (2 * n)
        t += [(a, a + 1, b + 1), (a, b + 1, b)]
    return Mesh(vertices=v, triangles=t, uvs=uv)


# =====================================================================
#  SAHNE: Güneş ve Samanyolu arka planı
# =====================================================================
class Gunes(Entity):
    """Güneş küresi: hareketli granülasyon + lekeler (GPU'da, ek doku gerektirmez)."""

    def __init__(self, doku):
        kw = {"shader": golge("gunes")} if GUNES_GOLGELENDIRICI else {}
        super().__init__(model="sphere", texture=doku, scale=7, **kw)
        self.sh = bool(kw)
        if self.sh:
            girdi(self, "zaman", 0.0)

    def update(self):
        if self.sh:
            girdi(self, "zaman", time.time() % 5000.0)


def sahne_kur():
    R = random.Random(11)
    Gunes(tex(dokular.gunes(R)))
    for olcek, a in ((16, .85), (34, .32)):
        Entity(model="quad", texture=Texture(dokular.parilti((255, 190, 90))), scale=olcek,
               billboard=True, color=Color(1, 1, 1, a))
    if UZAY_ARKAPLANI:
        Sky(texture=tex(dokular.uzay(R)), scale=1500)


# =====================================================================
#  TEK GEZEGEN
# =====================================================================
class Gezegen3B:
    def __init__(self, v, ozel=False, sira=0):
        self.v, self.ozel = v, ozel
        self.r = 0.5 * math.sqrt(v["yaricap_km"] / 6371)   # ekrana sığması için ölçekli
        self.d = 10 + math.sqrt(v["au"]) * 9                # yörünge yarıçapı (ölçekli)
        self.faz = sira * 1.15 + random.random()
        k = v["atm_k"]
        self.govde = kure(v, self.r, v["atm_renk"], k)
        self.govde.collider = "sphere"
        self.parcalar = [self.govde]

        # eksen eğikliği ve kendi etrafında dönme
        self.egim = float(ozellik(v, "egim", 0.0))
        self.donme_hizi = 25 * 24 / max(1.0, float(ozellik(v, "donme", 24.0)))
        self.aci = 0.0
        self.bulut_kayma = 0.0
        self.q_ok = Quat is not None
        if self.q_ok:
            self.egim_q = Quat()
            self.egim_q.setFromAxisAngle(self.egim, PVec3(0, 1, 0))

        # atmosfer ışıması
        self.atm = None
        if k > 0.02:
            self.atm = self.atmosfer_kur(k, v["atm_renk"])
            self.parcalar.append(self.atm)

        # bulut katmanı (Dünya)
        self.bulut = None
        dok = self.govde.dok
        if GOLGELEME and GELISMIS and dok.bulut is not None:
            bulut_tex = getattr(self.govde, "bulut_tex", None) or tex(dok.bulut)
            self.bulut = Entity(model="sphere", texture=bulut_tex, scale=self.r * 2.014,
                                shader=golge("bulut"), color=Color(1, 1, 1, .999))
            girdi(self.bulut, "bulut_ofs", 0.0)
            self.parcalar.append(self.bulut)

        # halka (dokulu, boşluklu, gezegenin gölgesi düşer)
        self.halka = None
        if v.get("halka"):
            kw = {"shader": golge("halka")} if (GOLGELEME and GELISMIS) else {}
            halka_dok = tex(dokular.halka_seridi(v["halka"]))
            self.halka = Entity(model=halka_mesh(self.r * 1.4, self.r * 2.5),
                                texture=halka_dok,
                                color=Color(1, 1, 1, .999), double_sided=True, **kw)
            if kw:
                girdi(self.halka, "pr", float(self.r))
                girdi(self.govde, "halka_var", 1.0)
                girdi(self.govde, "halka_map", halka_dok)
                girdi(self.govde, "halka_ic", float(self.r * 1.4))
                girdi(self.govde, "halka_dis", float(self.r * 2.5))
            if self.q_ok:
                self.halka.setQuat(self.egim_q)
            else:
                self.halka.rotation_x = self.egim
            self.parcalar.append(self.halka)

        # uydular
        self.aylar = []
        for ad, km, mesafe, per, renk in ozellik(v, "aylar", []):
            mr = max(.06, self.r * km / v["yaricap_km"])
            uv_ = {"ad": ad, "renk": renk, "doku": "kaya", "boyut": 1024}
            e = kure(uv_, mr, dok=dokular.doku_uret(uv_, ayri_bulut=False))
            self.aylar.append((e, mesafe * self.r + (self.r if self.halka else 0), per, random.random() * 6.28))

        pts = [Vec3(math.cos(i / 128 * 6.2832) * self.d, 0, math.sin(i / 128 * 6.2832) * self.d)
               for i in range(129)]
        self.yorunge = Entity(model=Mesh(vertices=pts, mode="line", thickness=1.5),
                              color=hx(v["renk"], .35))
        self.canli = [{"v": v[k_], "h": [v[k_]] * 40} for _, k_, _, _, _ in CANLI]

    def atmosfer_kur(self, k, renk):
        """Gezegen kenarından dışa taşan ışıma; olmazsa ince saydam kabuğa döner."""
        if GOLGELEME and GELISMIS and ATMOSFER_PARLAMA:
            try:
                from panda3d.core import ColorBlendAttrib, CullFaceAttrib
                s = 1.06 + k * 0.10
                e = Entity(model="sphere", scale=self.r * 2 * s, shader=golge("atm"))
                girdi(e, "atm_renk", dogrusal(renk))
                girdi(e, "atm_k", float(k))
                girdi(e, "atm_s", float(s))
                e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne,
                                                  ColorBlendAttrib.OOne))
                e.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
                e.setDepthWrite(False)
                e.setBin("fixed", 10)
                return e
            except Exception as hata:
                print("Atmosfer ışıması kurulamadı, basit kabuk kullanılıyor:", hata)
        return Entity(model="sphere", scale=self.r * 2 * (1.04 + k * 0.07),
                      color=hx(renk, 0.03 + k * 0.09))

    def guncelle(self, T, dt, donsun=True):
        """T: geçen gün. Gezegeni yörüngesindeki yerine koyar."""
        a = T / self.v["periyot"] * 2 * math.pi + self.faz
        p = Vec3(math.cos(a) * self.d, 0, math.sin(a) * self.d)
        for o in self.parcalar:
            o.position = p
        for e, mesafe, per, faz in self.aylar:
            b = T / per * 2 * math.pi + faz
            e.position = p + Vec3(math.cos(b) * mesafe, 0, math.sin(b) * mesafe)
        if donsun:
            self.aci = (self.aci + dt * self.donme_hizi) % 360
            self.bulut_kayma = (self.bulut_kayma + dt * self.donme_hizi * 0.06 / 360.0) % 1.0
        if GOLGELEME and GELISMIS:
            girdi(self.govde, "zaman", time.time() % 5000.0)
            ofs = (0.055 - self.bulut_kayma) % 1.0
            girdi(self.govde, "bulut_ofs", float(ofs))
            if self.bulut is not None:
                girdi(self.bulut, "bulut_ofs", float(ofs))
        if self.halka is not None and GOLGELEME and GELISMIS and self.q_ok:
            try:
                girdi(self.govde, "halka_n", self.egim_q.xform(PVec3(0, 0, 1)))
            except Exception:
                pass
        if self.q_ok:
            try:
                q = Quat()
                q.setFromAxisAngle(self.aci, PVec3(0, 0, 1))
                self.govde.setQuat(q * self.egim_q)
                if self.bulut is not None:
                    self.bulut.setQuat(q * self.egim_q)
                return
            except Exception:
                self.q_ok = False
        self.govde.rotation_y = self.aci

    def gercek_faz(self, boylam_derece, T):
        """Gezegeni, verilen T anında gerçek (Güneş merkezli ekliptik) boylamına yerleştirir."""
        self.faz = math.radians(boylam_derece) - T / self.v["periyot"] * 2 * math.pi

    def canli_guncelle(self):
        """Simüle canlı veri: gezegenin ortalama değeri etrafında dalgalanır."""
        for L, (_, k, _, mn, _) in zip(self.canli, CANLI):
            taban = self.v[k]
            sapma = max(abs(taban) * 0.04, mn)
            L["v"] += (taban + random.uniform(-1, 1) * sapma - L["v"]) * 0.4
            L["h"].append(L["v"])
            L["h"].pop(0)

    def sil(self):
        for o in self.parcalar + [self.yorunge] + [e for e, *_ in self.aylar]:
            destroy(o)
