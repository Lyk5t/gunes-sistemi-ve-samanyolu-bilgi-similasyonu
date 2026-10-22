-- Sağlık, İlaç ve Gıda Takip Asistanı - SQLite şeması
-- Tarihler ISO biçiminde metin olarak saklanır: 'YYYY-MM-DD' veya 'YYYY-MM-DD HH:MM:SS'.
-- Her bağlantıda foreign key desteğini açmak gerekir: PRAGMA foreign_keys = ON;
-- Temel ve basit sql yapısı geliştirilmesi gerekmektedir. 
PRAGMA foreign_keys = ON;

-- ÜRÜN: ilaç ve gıdalar
CREATE TABLE IF NOT EXISTS urun (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tur            TEXT    NOT NULL CHECK (tur IN ('ilac', 'gida')),
    ad             TEXT    NOT NULL CHECK (length(trim(ad)) > 0),
    barkod         TEXT,
    son_kullanma   TEXT    NOT NULL CHECK (date(son_kullanma) IS NOT NULL),
    miktar         TEXT,
    notlar         TEXT,
    eklenme_zamani TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_urun_son_kullanma ON urun (son_kullanma);
CREATE INDEX IF NOT EXISTS idx_urun_tur          ON urun (tur);

-- ALARM: her ürün için planlanan bildirimler (örn. 30, 7, 1 gün önce)
-- Sağlık, İlaç ve Gıda Takip Asistanı

CREATE TABLE IF NOT EXISTS alarm (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    urun_id          INTEGER NOT NULL REFERENCES urun (id) ON DELETE CASCADE,
    gun_once         INTEGER NOT NULL CHECK (gun_once >= 0),
    bildirim_zamani  TEXT    NOT NULL CHECK (datetime(bildirim_zamani) IS NOT NULL),
    bildirim_kimligi INTEGER,             -- işletim sisteminde planlanan bildirimin kimliği
    UNIQUE (urun_id, gun_once)
);

CREATE INDEX IF NOT EXISTS idx_alarm_urun_id ON alarm (urun_id);
CREATE INDEX IF NOT EXISTS idx_alarm_zaman   ON alarm (bildirim_zamani);

-- PROFİL: tek kayıt (id her zaman 1). Listeler JSON dizisi olarak tutulur.
CREATE TABLE IF NOT EXISTS profil (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    yas              INTEGER CHECK (yas IS NULL OR (yas >= 0 AND yas <= 120)),
    alerjiler        TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(alerjiler)),
    rahatsizliklar   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(rahatsizliklar)),
    duzenli_ilaclar  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(duzenli_ilaclar))
);

INSERT OR IGNORE INTO profil (id) VALUES (1);

-- ANA LİSTE GÖRÜNÜMÜ: kalan gün ve durum hesaplanmış halde
CREATE VIEW IF NOT EXISTS v_ana_liste AS
SELECT
    u.id,
    u.tur,
    u.ad,
    u.son_kullanma,
    u.miktar,
    CAST(julianday(u.son_kullanma) - julianday(date('now', 'localtime')) AS INTEGER) AS kalan_gun,
    CASE
        WHEN date(u.son_kullanma) <  date('now', 'localtime')                 THEN 'gecti'
        WHEN date(u.son_kullanma) <= date('now', 'localtime', '+7 days')      THEN 'yakin'
        ELSE 'iyi'
    END AS durum
FROM urun u
ORDER BY u.son_kullanma ASC;
