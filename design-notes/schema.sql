-- MenuFit-India core schema: data model + nutrition engine storage.
-- Postgres 15+, PostGIS (geo), pgvector (dish-name matching).
-- Numbers are only ever stored per recipe version; canonical dishes hold reference bands, never served values.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------- reference data

-- Which nutrient source a row came from, so licence status is auditable per value.
CREATE TABLE data_source (
    id             text PRIMARY KEY,            -- 'ifct2017', 'indb', 'house'
    name           text NOT NULL,
    licence_status text NOT NULL CHECK (licence_status IN ('pending', 'granted', 'reference_only', 'own')),
    licence_note   text
);

-- Raw-state ingredients only. Cooked values are computed, never stored here.
CREATE TABLE ingredient (
    id              bigserial PRIMARY KEY,
    source_id       text NOT NULL REFERENCES data_source(id),
    source_code     text,                      -- e.g. IFCT food code
    name            text NOT NULL,
    kcal_100g       numeric(7,2) NOT NULL,
    protein_100g    numeric(6,2) NOT NULL,
    fat_100g        numeric(6,2) NOT NULL,
    carb_100g       numeric(6,2) NOT NULL,
    fibre_100g      numeric(6,2),
    sodium_mg_100g  numeric(8,2),
    density_g_ml    numeric(5,3),
    edible_fraction numeric(4,3) NOT NULL DEFAULT 1 CHECK (edible_fraction > 0 AND edible_fraction <= 1),
    is_added_fat    boolean NOT NULL DEFAULT false, -- oil/ghee/butter/cream: asked for first in the builder
    db_version      text NOT NULL                -- bump when values change; part of the engine cache key
);

-- Local-language names and household measures ("1 katori dal", "1 chamach ghee").
CREATE TABLE ingredient_alias (
    id             bigserial PRIMARY KEY,
    ingredient_id  bigint NOT NULL REFERENCES ingredient(id),
    language       text NOT NULL,              -- BCP-47: 'hi', 'te', 'hi-Latn'
    text           text NOT NULL,
    household_unit text,
    grams_per_unit numeric(7,2)
);

-- Cooking transforms, keyed by method. Ranges are (min, mode, max).
CREATE TABLE cooking_method (
    id                text PRIMARY KEY,          -- 'deep_fry', 'tandoor', 'grill', 'simmer', 'raw'
    fat_absorb_min    numeric(4,3) NOT NULL DEFAULT 0,  -- oil taken up, fraction of food weight
    fat_absorb_mode   numeric(4,3) NOT NULL DEFAULT 0,
    fat_absorb_max    numeric(4,3) NOT NULL DEFAULT 0,
    yield_factor      numeric(4,3) NOT NULL DEFAULT 1   -- cooked weight / raw weight
);

-- ---------------------------------------------------------------- dishes and outlets

CREATE TABLE canonical_dish (
    id                 bigserial PRIMARY KEY,
    name               text NOT NULL,
    region             text,                    -- 'hyderabad', 'kolkata', NULL = pan-India
    aliases            text[] NOT NULL DEFAULT '{}',
    name_embedding     vector(768),
    -- Reference band per 100 g, built from Tier A/B declarations only (see dish_reference_band view).
    -- Seeded by the house nutritionist set until enough verified data exists.
    ref_kcal_p10_100g  numeric(7,2),
    ref_kcal_p50_100g  numeric(7,2),
    ref_kcal_p90_100g  numeric(7,2)
);
CREATE INDEX ON canonical_dish USING hnsw (name_embedding vector_cosine_ops);

CREATE TABLE brand (
    id   bigserial PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE outlet (
    id            bigserial PRIMARY KEY,
    brand_id      bigint REFERENCES brand(id),
    name          text NOT NULL,
    fssai_licence text,
    phone         text,
    location      geography(Point, 4326) NOT NULL,
    closed_at     timestamptz
);
CREATE INDEX ON outlet USING gist (location);
CREATE UNIQUE INDEX outlet_fssai_uniq ON outlet (fssai_licence) WHERE fssai_licence IS NOT NULL;

CREATE TABLE menu_item (
    id                bigserial PRIMARY KEY,
    outlet_id         bigint NOT NULL REFERENCES outlet(id),
    canonical_dish_id bigint REFERENCES canonical_dish(id),
    display_name      text NOT NULL,
    price_inr         numeric(8,2),
    serving_grams     numeric(7,1),
    serving_unit      text,                     -- 'plate', 'katori', 'piece'
    diet              text NOT NULL CHECK (diet IN ('veg', 'egg', 'non_veg')),
    diet_tags         text[] NOT NULL DEFAULT '{}', -- 'jain', 'no_onion_garlic', 'vrat', 'halal'
    current_version   bigint                    -- FK added below
);

-- ---------------------------------------------------------------- recipes (immutable)

CREATE TABLE recipe_version (
    id                bigserial PRIMARY KEY,
    menu_item_id      bigint REFERENCES menu_item(id),  -- NULL for brand templates / regional templates
    brand_id          bigint REFERENCES brand(id),
    canonical_dish_id bigint REFERENCES canonical_dish(id),
    parent_version_id bigint REFERENCES recipe_version(id), -- inherit lines from brand template
    batch_yield_grams numeric(8,1),
    servings_per_batch numeric(6,2) NOT NULL DEFAULT 1,
    declared_by       text NOT NULL,             -- user id, 'house', 'ai_extraction'
    declared_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE recipe_line (
    id                bigserial PRIMARY KEY,
    version_id        bigint NOT NULL REFERENCES recipe_version(id),
    line_key          text NOT NULL,             -- stable across versions; outlet overrides match on it
    ingredient_id     bigint NOT NULL REFERENCES ingredient(id),
    qty_min_g         numeric(8,2) NOT NULL,
    qty_mode_g        numeric(8,2) NOT NULL,
    qty_max_g         numeric(8,2) NOT NULL,
    stage             text NOT NULL,             -- 'marinade', 'gravy', 'tadka', 'finish'
    method_id         text NOT NULL REFERENCES cooking_method(id),
    removed           boolean NOT NULL DEFAULT false, -- override: drop an inherited line
    CHECK (qty_min_g <= qty_mode_g AND qty_mode_g <= qty_max_g),
    UNIQUE (version_id, line_key)
);

ALTER TABLE menu_item ADD FOREIGN KEY (current_version) REFERENCES recipe_version(id);

-- Every shown number must be traceable: recipes are append-only.
CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is immutable; create a new recipe_version instead', TG_TABLE_NAME;
END $$;
CREATE TRIGGER recipe_version_immutable BEFORE UPDATE OR DELETE ON recipe_version
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER recipe_line_immutable BEFORE UPDATE OR DELETE ON recipe_line
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------------------------------------------------------------- modifiers

-- Exclusive groups: at most one modifier per group (e.g. 'oil_level': less oil | no oil).
CREATE TABLE modifier_group (
    id           bigserial PRIMARY KEY,
    menu_item_id bigint NOT NULL REFERENCES menu_item(id),
    name         text NOT NULL,
    exclusive    boolean NOT NULL DEFAULT true
);

CREATE TABLE modifier (
    id          bigserial PRIMARY KEY,
    group_id    bigint NOT NULL REFERENCES modifier_group(id),
    label       text NOT NULL,                   -- 'Less oil', 'Grilled instead of fried'
    kind        text NOT NULL CHECK (kind IN ('delta', 'method_swap')),
    -- 'requested' = kitchen may not comply; 'measured' = portioned/controlled change.
    assurance   text NOT NULL CHECK (assurance IN ('requested', 'measured')),
    -- delta:       [{"line_key": "butter", "scale": 0.5}] or [{"line_key": "ghee_roti", "add_g": [3,5,8], "ingredient_id": 12}]
    -- method_swap: {"stage": "fry", "method_id": "grill"}
    spec        jsonb NOT NULL
);

-- ---------------------------------------------------------------- evidence and trust

CREATE TABLE evidence (
    id          bigserial PRIMARY KEY,
    version_id  bigint NOT NULL REFERENCES recipe_version(id),
    kind        text NOT NULL CHECK (kind IN ('lab_report', 'audit', 'owner_attestation', 'user_report', 'photo')),
    polarity    smallint NOT NULL DEFAULT 1 CHECK (polarity IN (-1, 1)), -- user mismatch reports are -1
    weight      numeric(4,2) NOT NULL DEFAULT 1,  -- reporter reputation for user reports
    detail      jsonb,                            -- lab values, report text, geo-proof
    recorded_at timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz
);

-- Tier is derived from evidence, never set by hand.
CREATE VIEW recipe_tier AS
SELECT v.id AS version_id,
       CASE
         WHEN bool_or(e.kind = 'lab_report' AND e.polarity = 1 AND e.expires_at > now()) THEN 'A'
         WHEN bool_or(e.kind = 'audit' AND e.polarity = 1 AND e.expires_at > now())
          AND bool_or(e.kind = 'owner_attestation' AND e.expires_at > now()) THEN 'B'
         WHEN bool_or(e.kind = 'owner_attestation' AND e.expires_at > now()) THEN 'C'
         ELSE 'D'
       END AS tier,
       coalesce(sum(e.weight) FILTER (WHERE e.kind = 'user_report' AND e.polarity = -1), 0) AS negative_report_weight
FROM recipe_version v
LEFT JOIN evidence e ON e.version_id = v.id
GROUP BY v.id;

-- ---------------------------------------------------------------- engine output (cache)

-- Key includes engine and ingredient-DB versions: an immutable recipe is not an immutable result
-- if IFCT values or yield factors are corrected.
CREATE TABLE computed_nutrition (
    version_id        bigint NOT NULL REFERENCES recipe_version(id),
    modifier_set      bigint[] NOT NULL DEFAULT '{}',  -- sorted modifier ids
    engine_version    text NOT NULL,
    ingredient_db_ver text NOT NULL,
    tier              char(1) NOT NULL,
    serving_grams     numeric(7,1),
    kcal              numeric(7,1)[3] NOT NULL,        -- {p10, p50, p90}
    protein_g         numeric(6,1)[3] NOT NULL,
    fat_g             numeric(6,1)[3] NOT NULL,
    carb_g            numeric(6,1)[3] NOT NULL,
    display_mode      text NOT NULL CHECK (display_mode IN ('single', 'band', 'range', 'range_unranked')),
    plausibility_flag boolean NOT NULL DEFAULT false,
    computed_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (version_id, modifier_set, engine_version, ingredient_db_ver)
);

-- Precomputed best Healthify swap, per dish and goal (fat-loss and protein users want different swaps).
CREATE TABLE healthify_suggestion (
    menu_item_id bigint NOT NULL REFERENCES menu_item(id),
    goal         text NOT NULL CHECK (goal IN ('fat_loss', 'protein', 'maintain', 'diabetic')),
    modifier_set bigint[] NOT NULL,
    kcal_saved   numeric(6,1),
    protein_delta numeric(6,1),
    computed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (menu_item_id, goal)
);

-- ---------------------------------------------------------------- tunable thresholds

CREATE TABLE engine_config (
    key   text PRIMARY KEY,
    value numeric NOT NULL,
    note  text
);
INSERT INTO engine_config VALUES
  ('band_ratio',             1.25, 'P90/P10 kcal above this: show number with band'),
  ('range_ratio',            1.50, 'above this: range only, no midpoint'),
  ('unranked_ratio',         2.50, 'above this: excluded from fit rankings...'),
  ('unranked_min_width_kcal', 150, '...but only if P90-P10 is also at least this wide'),
  ('hysteresis',             0.05, 'ratio must cross a boundary by this much to change mode'),
  ('requested_compliance',   0.70, 'chance the kitchen honours a requested (unmeasured) modifier');

-- ---------------------------------------------------------------- reference bands

-- Each dish's spread from verified declarations only. Self-declared (C) and AI (D) data are excluded,
-- otherwise under-declaring restaurants drag the band down and the plausibility check becomes circular.
CREATE VIEW dish_reference_band AS
SELECT rv.canonical_dish_id,
       count(*) AS n_verified,
       percentile_cont(0.1) WITHIN GROUP (ORDER BY cn.kcal[2] * 100 / cn.serving_grams) AS kcal_p10_100g,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY cn.kcal[2] * 100 / cn.serving_grams) AS kcal_p50_100g,
       percentile_cont(0.9) WITHIN GROUP (ORDER BY cn.kcal[2] * 100 / cn.serving_grams) AS kcal_p90_100g
FROM computed_nutrition cn
JOIN recipe_version rv ON rv.id = cn.version_id
WHERE cn.tier IN ('A', 'B') AND cn.modifier_set = '{}' AND cn.serving_grams > 0
GROUP BY rv.canonical_dish_id;
