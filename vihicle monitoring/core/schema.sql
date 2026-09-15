-- auto.ria catalogue: current state of the offers plus the history of changes.
--
-- Data arrives from GraphQL advertisements(ids:[...]). The UsedAuto type has 37
-- fields but fewer useful ones: statistic, version and autoBuy are always NULL
-- without authorisation, and prices refers to paying for placement rather than
-- to the car. What is left here is what makes sense to search and count on.
--
-- What the API does NOT have (verified by schema introspection):
--   * the seller's description, that field is absent from UsedAuto entirely;
--   * a damage flag, Labels{damage} exists but hangs on the InfoType type,
--     which no query returns; an orphan type.
--   * the site's own price history, ChangesHistory sits on InfoType as well.
-- The first two live only on the HTML page of the ad (ld+json), the third we
-- build ourselves, which is what car_history exists for.


-- Body type dictionary. Body in GraphQL returns only {id} with no name, so the
-- names were taken from /api/categories/{id}/bodystyles and put here once:
-- otherwise every record would need a network round trip for the dictionary.
CREATE TABLE IF NOT EXISTS body_types (
    body_id smallint PRIMARY KEY,
    name    text NOT NULL
);

INSERT INTO body_types (body_id, name) VALUES
    (2, 'Універсал'),
    (3, 'Седан'),
    (4, 'Хетчбек'),
    (5, 'Позашляховик / Кросовер'),
    (6, 'Купе'),
    (7, 'Кабріолет'),
    (8, 'Мінівен'),
    (9, 'Пікап'),
    (11, 'Скутер'),
    (12, 'Максі-скутер'),
    (13, 'Мотоцикли'),
    (14, 'Мотоцикл Классік'),
    (15, 'Мотоцикл Без обтікачів (Naked bike)'),
    (16, 'Мотоцикл Туризм'),
    (17, 'Мотоцикл Спорт-туризм'),
    (18, 'Спортбайк'),
    (19, 'Мотоцикл Кросс'),
    (20, 'Мотоцикл Тріал'),
    (21, 'Мотоцикл Позашляховий (Enduro)'),
    (22, 'Мотоцикл Супермото (Motard)'),
    (23, 'Мотоцикл Чоппер'),
    (24, 'Мотоцикл Круізер'),
    (25, 'Мотоцикл Багатоцільовий (All-round)'),
    (29, 'Мотоцикл з коляскою'),
    (30, 'Мотоцикл Кастом'),
    (31, 'Міні мотоцикли'),
    (32, 'Міні спорт'),
    (33, 'Пітбайк'),
    (34, 'Трицикл'),
    (35, 'Квадроцикли'),
    (36, 'Квадроцикл дитячий'),
    (39, 'Квадроцикл спортивний'),
    (41, 'Квадроцикл утилітарний'),
    (42, 'Мотовсюдиход'),
    (43, 'Всюдихід-амфібія'),
    (44, 'Гольф-кар'),
    (45, 'Картинг'),
    (46, 'Снігохід'),
    (51, 'Гідроцикли'),
    (53, 'Гідроцикл спортивний'),
    (55, 'Гідроцикл туристичний'),
    (56, 'Інший мототранспорт'),
    (57, 'Трайк'),
    (58, 'Мопеди'),
    (59, 'Човен'),
    (61, 'Катер'),
    (62, 'Моторна яхта'),
    (63, 'Парусна яхта'),
    (64, 'Інший водний транспорт'),
    (66, 'Трактор сільськогосподарський'),
    (68, 'Мінітрактор'),
    (69, 'Мотоблок / Мотокультиватор'),
    (70, 'Комбайн'),
    (71, 'Сівалка'),
    (72, 'Плуг'),
    (73, 'Обприскувач'),
    (74, 'Грунтообробна техніка'),
    (77, 'Кормозбиральна техніка'),
    (79, 'Садова техніка'),
    (80, 'Будівельна техніка'),
    (81, 'Екскаватор'),
    (84, 'Міні-екскаватор'),
    (86, 'Бульдозер'),
    (87, 'Автокран'),
    (88, 'Баштовий кран'),
    (89, 'Автогрейдер'),
    (90, 'Аварійно-ремонтні машини'),
    (91, 'Гудронатор'),
    (92, 'Асфальтозавод'),
    (93, 'Асфальтоукладчик'),
    (95, 'Бетононасос'),
    (96, 'Бетоноукладач'),
    (98, 'Бурова установка'),
    (99, 'Сваебій / Дизельний молот'),
    (100, 'Дорожній каток'),
    (101, 'Компресор'),
    (102, 'Мотопомпа / Насос'),
    (103, 'Ресайклер'),
    (105, 'Фреза дорожня'),
    (106, 'Електростанція / Генератор'),
    (107, 'Інша будівельна техніка'),
    (109, 'Складський навантажувач / Штабелер'),
    (111, 'Підйомник'),
    (114, 'Навантажувачі'),
    (115, 'Фронтальні навантажувачі'),
    (116, 'Міні-вантажник'),
    (118, 'Телескопічні навантажувачі'),
    (120, 'Контейнерний навантажувач'),
    (121, 'Комунальна техніка'),
    (122, 'Машина аварійно-ремонтна "МАВР"'),
    (123, 'Прибирально-поливальні автомобілі'),
    (124, 'Автовишка'),
    (125, 'Машина  асенізатор (вакуумна)'),
    (126, 'Мулокачальна машина'),
    (127, 'Сміттєвоз'),
    (128, 'Каналопромивочна машина'),
    (129, 'Піскорозкидальна машина'),
    (130, 'Прибиральна машина'),
    (131, 'Снігоприбиральна машина'),
    (132, 'Спецтранспорт'),
    (133, 'Всюдихід'),
    (134, 'Харвестер / форвардер'),
    (135, 'Баггі / Гоночний автомобіль'),
    (136, 'Спеціальний автобус'),
    (137, 'Автомобіль швидкої допомоги'),
    (138, 'Броньований автомобіль'),
    (140, 'Інша спецтехніка'),
    (142, 'Пожежна машина'),
    (145, 'Бетонозмішувач (Міксер)'),
    (146, 'Скрепер'),
    (147, 'Прицеп'),
    (148, 'Шасі'),
    (149, 'Платформа'),
    (150, 'Борт'),
    (151, 'Тентований борт (штора) - прицеп'),
    (152, 'Самоскид причіп'),
    (153, 'Фургон'),
    (154, 'Контейнеровоз'),
    (155, 'Цистерна'),
    (157, 'Рефрижератор'),
    (159, 'Для перевезення тварин - прицеп'),
    (160, 'Лісовоз / Сортиментовоз - прицеп'),
    (161, 'Напівпричіп'),
    (162, 'Шассі напівпричіп'),
    (163, 'Платформа напівпричіп'),
    (164, 'Низкорамна платформа'),
    (165, 'Бортовий напівпричіп'),
    (167, 'Тентований борт (штора) - напівпричіп'),
    (168, 'Самоскид напівпричіп'),
    (169, 'Контейнеровоз напівпричіп'),
    (170, 'Фургон напівпричіп'),
    (171, 'Цистерна напівпричіп'),
    (172, 'Бетономішалка (Міксер) напівпричіп'),
    (173, 'Рефрижератор напівпричіп'),
    (175, 'Лісовоз / Сортиментовоз - напівпричіп'),
    (176, 'Для перевезення тварин - напівпричіп'),
    (177, 'Плитовоз'),
    (178, 'Автовоз'),
    (179, 'Легковий причіп'),
    (190, 'Вантажівка'),
    (192, 'Шасі'),
    (193, 'Платформа'),
    (194, 'Борт'),
    (195, 'Тентований'),
    (196, 'Самоскид'),
    (197, 'Вантажний фургон'),
    (198, 'Рефрижератор'),
    (200, 'Контейнеровоз'),
    (201, 'Цистерна'),
    (202, 'Бетономішалка (Міксер)'),
    (203, 'Для перевезення тварин'),
    (204, 'Лісовоз / Сортиментовоз'),
    (205, 'Мультиліфт'),
    (206, 'Скловоз'),
    (207, 'Автовоз'),
    (208, 'Евакуатор'),
    (210, 'Мікроавтобус вантажний (до 3,5т)'),
    (211, 'Сміттєвоз'),
    (212, 'Тягач'),
    (213, 'Інші вантажівки'),
    (219, 'Мікроавтобус'),
    (220, 'Автобус'),
    (221, 'Міський автобус'),
    (224, 'Приміський автобус'),
    (227, 'Туристичний / Міжміський автобус'),
    (228, 'Вахтове авто / Кунг'),
    (229, 'Інші автобуси'),
    (250, 'Екскаватор навантажувач'),
    (251, 'Інші причепи'),
    (252, 'Лімузин'),
    (254, 'Вантажопасажирський фургон'),
    (255, 'Причіп дача'),
    (256, 'Лафет'),
    (257, 'Будинок на колесах'),
    (258, 'Мобільний будинок'),
    (259, 'Літак'),
    (298, 'Евакуатор'),
    (299, 'Кран-маніпулятор'),
    (300, 'Вертоліт'),
    (301, 'Дельтаплан'),
    (302, 'Інший повітряний транспорт'),
    (303, 'Ізотермічна будка'),
    (304, 'Земснаряд'),
    (305, 'Гастрономія'),
    (306, 'RIB'),
    (307, 'Ліфтбек'),
    (308, 'Катафалк'),
    (309, 'Комбайн кормозбиральний'),
    (310, 'Комбайн зернозбиральний'),
    (311, 'Обприскувачі самохідні'),
    (312, 'Обприскувачі причіпні'),
    (313, 'Плуг оборотний'),
    (314, 'Кормовоз'),
    (315, 'Родстер'),
    (316, 'Борона'),
    (317, 'Жатка для збирання врожаю'),
    (318, 'Граблі ворушилки'),
    (319, 'Сінокосарка'),
    (320, 'Культиватор'),
    (321, 'Посівний комплекс'),
    (322, 'Грунтофреза'),
    (323, 'Прес-підбирач'),
    (324, 'Ремонтно-майстерний фургон'),
    (325, 'Розпушувач грунту та землі'),
    (326, 'Скіддер (трелювальний трактор)'),
    (327, 'Візок для жатки'),
    (328, 'Трубоукладач'),
    (329, 'Ущільнювач'),
    (330, 'Цементовоз'),
    (331, 'Колісний екскаватор'),
    (332, 'Гусеничний екскаватор'),
    (333, 'Зернова жатка'),
    (334, 'Жатка для збирання кукурудзи'),
    (335, 'Жатка для збирання соняшника'),
    (336, 'Вилочний навантажувач'),
    (337, 'Штабелер'),
    (338, 'Комбайн причіпний'),
    (339, 'Комбайн навісний'),
    (340, 'Дискова борона'),
    (341, 'Пружинна борона'),
    (342, 'Зубова борона'),
    (343, 'Ротаційна борона'),
    (344, 'Лущильник дисковий'),
    (345, 'Каток сільськогосподарський'),
    (346, 'Мульчувач'),
    (347, 'Сівалка суцільного висіву механічна'),
    (348, 'Сівалка суцільного висіву пневматична'),
    (349, 'Сівалка точного висіву пневматична'),
    (350, 'Сівалка точного висіву механічна'),
    (351, 'Розкидач мінерального добрива'),
    (352, 'Прес- підбирач тюковий'),
    (353, 'Прес-підбирач рулонний'),
    (354, 'ВПМ (валочно-пакетувальна машина і техніка)'),
    (355, 'Корчеватель, подрібнювач пнів (фреза)'),
    (356, 'Картоплесаджалка, машина для посадки картоплі'),
    (357, 'Картоплекопач'),
    (358, 'Зерноочисна машина'),
    (359, 'Зернокидач, зернопогрузчик'),
    (360, 'Дощувальна машина і установка'),
    (361, 'Земснаряд'),
    (362, 'Драглайн'),
    (363, 'Траншеєкопач'),
    (364, 'Ножичний підйомник'),
    (365, 'Трамбувальник (вібронога)'),
    (366, 'Малогабаритна бурова установка (міні)'),
    (367, 'Дробарка (дробильна установка)'),
    (368, 'Затиральна машина для стяжки і бетону'),
    (369, 'Штукатурна машина'),
    (373, 'Причіпний міні екскаватор'),
    (374, 'Колінчатий підйомник'),
    (375, 'Приймальний бункер'),
    (379, 'Ріпаковий стіл'),
    (380, 'Розкидувач органічних добрив'),
    (381, 'Гноєрозкидач'),
    (382, 'Стерньовий передпосівний культиватор'),
    (383, 'Зерносушарка / Мобільна зерносушарка'),
    (384, 'Трактор'),
    (385, 'Зерновоз'),
    (386, 'Зерновоз - причіп'),
    (387, 'Зерновоз - напівпричіп'),
    (388, 'Мототрактор'),
    (389, 'Дровокол'),
    (390, 'Трактор-газонокосарка'),
    (391, 'Комбайн картоплезбиральний'),
    (392, 'Подрібнювач гілок'),
    (393, 'Щепоріз'),
    (394, 'Морковоуборочний комбайн'),
    (395, 'Обприскувач навісний'),
    (396, 'Газонокосарка'),
    (397, 'Бурякозбиральний комбайн'),
    (398, 'Машини для видалення бадилля'),
    (399, 'Гребнеутворювач'),
    (400, 'Агрегат комбінований передпосівний'),
    (401, 'Підйомник телескопічний'),
    (402, 'Міні земснаряд'),
    (403, 'Каток ґрунтовий'),
    (404, 'Електровізок'),
    (405, 'Рокла, візок гідравлічний'),
    (406, 'Грохот вібраційний'),
    (407, 'Установки для горизонтального буріння'),
    (408, 'Грунтообробна'),
    (409, 'Трактори'),
    (410, 'Посівна і посадкова'),
    (411, 'Лісозаготівельна'),
    (412, 'Комбайни'),
    (413, 'Картопляна'),
    (414, 'Жатки'),
    (415, 'Для саду і городу'),
    (416, 'Для післязбиральної обробки'),
    (417, 'Для поливу і зрошення'),
    (418, 'Для заготівлі сіна'),
    (419, 'Для тваринництва'),
    (420, 'Для внесення добрив'),
    (421, 'Боббер'),
    (422, 'Скремблер'),
    (423, 'Кафе рейсер'),
    (424, 'Мотобуксир'),
    (425, 'Скутер ретро'),
    (426, 'Скутер для інвалідів'),
    (427, 'Мокик'),
    (428, 'Вантажні трицикли'),
    (429, 'Вантажні моторолери, мотоцикли, скутери, мопеди'),
    (430, 'Скутери з кабіною'),
    (431, 'Утилітарні снігоходи'),
    (432, 'Міні-розбірні снігоходи'),
    (433, 'Снігоходи для полювання та рибалки'),
    (434, 'Гірські снігоходи'),
    (435, 'Спортивні снігоходи'),
    (436, 'Снігомопеди та снігоскутери'),
    (437, 'Бітумовоз'),
    (438, 'Газовоз'),
    (439, 'Трубовоз'),
    (440, 'Металовоз'),
    (441, 'Бензовоз'),
    (442, 'Рибовоз'),
    (443, 'Міні кран'),
    (444, 'Підмітальна машина'),
    (445, 'Поливомийна машина'),
    (446, 'Солерозкидач'),
    (448, 'Фастбек'),
    (449, 'Мікровен'),
    (450, 'Хлібовоз'),
    (451, 'Агродрон'),
    (452, 'Моторолер'),
    (453, 'Скутери / Мопеди'),
    (454, 'Тарга')
ON CONFLICT (body_id) DO UPDATE SET name = EXCLUDED.name;


-- Current state of every ad, one row per car_id.
CREATE TABLE IF NOT EXISTS cars (
    -- The ad id on auto.ria. One physical car can be relisted under a new id,
    -- so "the same car" is decided by vin_masked rather than by this key.
    car_id         bigint PRIMARY KEY,

    -- The VIN arrives partly masked: WA1LAAF7xHDxxxx60, 12 of 17 characters
    -- are visible. The mask is deterministic (checked: the same string across
    -- requests), so it is enough for linking relistings. Not enough for legal
    -- identification: the full VIN is only in the ld+json on the ad page.
    vin_masked     text,

    -- Which marketplace the ad came from. Each scraper writes its own value.
    source         text NOT NULL DEFAULT 'auto.ria',

    -- A print of the CAR itself, not of the ad: sha256 over (vin_masked,
    -- brand_id, model_id, year). Deliberately without price, mileage or
    -- status, since those change on the very same car and would make the
    -- print useless.
    --
    -- It is what stitches one car across marketplaces and across relistings.
    -- vin_masked alone will not do: auto.ria hides 5 of 17 characters, and
    -- over 320k rows that produced 20,250 groups where DIFFERENT models sit
    -- under one masked VIN. Adding brand, model and year removes every one of
    -- those collisions.
    fingerprint    bytea,

    title          text NOT NULL,

    -- integer rather than smallint: some brands have ids past 55,000 (checked
    -- against the live feed), so a two-byte integer overflows on batch one.
    brand_id       integer,
    brand          text,
    model_id       integer,
    model          text,
    category_id    smallint,
    -- Deliberately WITHOUT an FK to body_types: the dictionary is a snapshot
    -- of the API, and if a new body id shows up tomorrow, the FK violation
    -- would roll back the whole batch. avnet already burned us on this, an
    -- orphaned id beats a lost batch.
    body_id        smallint,
    year           smallint,

    -- The API gives mileage in thousands of km (169 = 169k), converted to km
    -- here. That adds no precision, the rounding to a thousand stays.
    mileage_km     integer,

    fuel_id        smallint,
    fuel           text,
    gearbox        text,
    engine_liters  numeric(4, 2),

    -- engine{power{hp kW}} in GraphQL. Filled in roughly 40% of the ads
    -- (measured on 450 across categories), and where it is missing the API
    -- sends a zero instead of null, so build_row turns that zero into NULL: a
    -- car with 0 hp does not exist, and the zeros would drag every average
    -- down. What the seller types is not checked by the site either, so
    -- db.py throws out the displacement typed into the power box (1.5 l and
    -- "1500 hp") and anything above 2000.
    --
    -- Deliberately outside the change hash: power belongs to the car, not to
    -- the ad, so it has no business writing history rows.
    --
    -- Still dirty despite that: an electric scooter under 2000 carries watts,
    -- not horsepower. Category 2 with an electric fuel needs its own rule,
    -- there is no way to tell a 1200 W scooter from 1200 hp by the number.
    power_hp       smallint,
    power_kw       smallint,

    -- The price in three currencies arrives already computed by the server,
    -- so all three are stored: recomputing later at the day's rate would give
    -- different numbers than the buyer saw. currency is the one the seller
    -- listed in.
    -- The price IN THE currency the seller listed it in. The only number here
    -- that does not move on its own: usd/uah/eur are recalculated by the
    -- server at the current rate on every request, so they differ between two
    -- neighbouring runs in 96-98% of rows and cannot be used to detect a real
    -- price change.
    price_main     integer,
    price_usd      integer,
    price_uah      integer,
    price_eur      integer,
    currency       text,

    city_id        integer,
    city           text,
    state_id       integer,
    state          text,

    seller_id      bigint,
    seller_name    text,
    -- Rating.average is non-nullable while ~86% of sellers have no rating, so
    -- the server returns an error and nulls the whole subobject. Just NULL.
    seller_rating  numeric(3, 2),
    seller_reviews integer,
    seller_company text,
    is_dealer      boolean NOT NULL DEFAULT false,

    -- photos.all consistently returns exactly 5 shots no matter how many the
    -- ad holds. The full list comes only from the page's ld+json.
    photo_main     text,
    photos         jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- The raw value of the custom field. Judging by the customs_cleared
    -- filter on the site, 0 = cleared; the mapping is undocumented, hence a
    -- number rather than a boolean.
    customs_code   smallint,
    abroad         boolean,
    country_import smallint,

    -- Paid promotion level. The values are inconsistent (52, 80 and 112 all
    -- turn up in the feed), so it is stored as is. Useful as a sign the ad is
    -- promoted: those sit higher more often and change price more often.
    promo_level    smallint,

    status         text NOT NULL,
    url            text,

    listed_at      timestamptz,
    published_at   timestamptz,
    expires_at     timestamptz,

    -- sha256 over the fields that move (price, status, mileage, promo level).
    -- The upsert touches updated_at only when the hash changed, and the same
    -- hash never lands in car_history twice.
    data_hash      bytea NOT NULL,

    first_seen_at  timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    -- Unlike updated_at, rewritten on every run: falling behind now() is
    -- precisely the sign of an ad that vanished from the feed.
    last_seen_at   timestamptz NOT NULL DEFAULT now()
);

-- last_seen_at is rewritten for every row on every run, so leave room on the
-- pages for HOT updates instead of letting the table sprawl.
ALTER TABLE cars SET (fillfactor = 70);

-- For databases created before source/fingerprint existed.
ALTER TABLE cars ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'auto.ria';
ALTER TABLE cars ADD COLUMN IF NOT EXISTS fingerprint bytea;
ALTER TABLE car_history ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'auto.ria';

-- For databases created before price_main. Conditional so as not to take a
-- lock for nothing (ADD COLUMN is cheap, but the habit is worth keeping).
ALTER TABLE cars ADD COLUMN IF NOT EXISTS price_main integer;
ALTER TABLE car_history ADD COLUMN IF NOT EXISTS price_main integer;

-- For databases created before engine power was collected. The columns fill
-- themselves on the next pass: the upsert writes every updatable column no
-- matter whether data_hash moved.
ALTER TABLE cars ADD COLUMN IF NOT EXISTS power_hp smallint;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS power_kw smallint;

-- For databases created while brand_id was still smallint.
--
-- The condition here is not cosmetic. A bare ALTER ... TYPE takes ACCESS
-- EXCLUSIVE and rewrites the table EVERY time, even when there is nothing to
-- change. Let one backend sit idle in transaction and the ALTER queues up,
-- and behind it every subsequent query to cars joins the same queue: the
-- database looks dead while nobody is doing anything. That is exactly how it
-- happened once.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cars'
          AND column_name = 'brand_id'
          AND data_type = 'smallint'
    ) THEN
        ALTER TABLE cars ALTER COLUMN brand_id TYPE integer;
    END IF;
END $$;

-- For the future Telegram bot: brand+model, price, year, mileage, city.
CREATE INDEX IF NOT EXISTS idx_cars_vin        ON cars (vin_masked) WHERE vin_masked IS NOT NULL;
-- The core of cross-marketplace duplicate search: one car on auto.ria and on
-- otomoto yields the same fingerprint, and finding the pair is a single JOIN.
CREATE INDEX IF NOT EXISTS idx_cars_fingerprint ON cars (fingerprint) WHERE fingerprint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cars_source      ON cars (source);
CREATE INDEX IF NOT EXISTS idx_cars_brand      ON cars (brand_id, model_id);
CREATE INDEX IF NOT EXISTS idx_cars_price      ON cars (price_usd);
CREATE INDEX IF NOT EXISTS idx_cars_year       ON cars (year);
CREATE INDEX IF NOT EXISTS idx_cars_mileage    ON cars (mileage_km);
-- Partial: about 60% of the rows have no power at all, and they have no place
-- in an index nobody will search through.
CREATE INDEX IF NOT EXISTS idx_cars_power      ON cars (power_hp) WHERE power_hp IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cars_city       ON cars (city_id);
CREATE INDEX IF NOT EXISTS idx_cars_updated    ON cars (updated_at DESC);
-- Partial: they cover only the working part of the table, so they cost little.
CREATE INDEX IF NOT EXISTS idx_cars_active     ON cars (last_seen_at) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_cars_search     ON cars (brand_id, model_id, year, price_usd) WHERE status = 'ACTIVE';


-- Offer history: one row per observed state of an ad.
--
-- Written only when data_hash changed, so the table grows with real price or
-- status changes rather than with the number of runs.
CREATE TABLE IF NOT EXISTS car_history (
    history_id  bigserial PRIMARY KEY,

    -- Deliberately WITHOUT an FK to cars: the history has to outlive the ad's
    -- removal from the active table, or it loses its point exactly when it
    -- starts being interesting.
    car_id      bigint NOT NULL,

    -- The second linking key. When the same car is relisted under a new
    -- car_id, this is all that stays shared, and it is what stitches the
    -- resale history: SELECT ... WHERE vin_masked = ... ORDER BY recorded_at.
    vin_masked  text,

    price_usd   integer,
    price_uah   integer,
    status      text,
    promo_level smallint,

    -- A full snapshot of the row at that moment: the cars schema will keep
    -- changing, and history cannot be rewritten after the fact.
    snapshot    jsonb NOT NULL,

    data_hash   bytea NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),

    -- This key is what deduplicates: a repeat run with the same state adds
    -- nothing, because (car_id, data_hash) is already there.
    UNIQUE (car_id, data_hash)
);

CREATE INDEX IF NOT EXISTS idx_hist_car   ON car_history (car_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_hist_vin   ON car_history (vin_masked, recorded_at DESC) WHERE vin_masked IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_hist_time  ON car_history (recorded_at DESC);


-- The incremental scan boundary. order_by=7 in search sorts strictly by the
-- ad's bump time, and that very time is what arrives in createdAt. So the
-- boundary is kept as a time, not as the last id: ids in the feed are not
-- ordered, and any single ad can vanish from it or float up after a bump.
--
-- boundary_at is the head time of the feed as of the PREVIOUS completed run.
-- Written only once a run reached the boundary or the end of the category: an
-- interrupted run has no right to move it, otherwise the range it did not
-- manage to collect is lost for good.
CREATE TABLE IF NOT EXISTS scan_state (
    source      text NOT NULL,
    category_id smallint NOT NULL,
    boundary_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, category_id)
);

-- For reading the boundary and for the weekly pass over vanished ads.
CREATE INDEX IF NOT EXISTS idx_cars_cat_listed ON cars (category_id, listed_at DESC);
CREATE INDEX IF NOT EXISTS idx_cars_seen       ON cars (source, last_seen_at) WHERE status = 'ACTIVE';
