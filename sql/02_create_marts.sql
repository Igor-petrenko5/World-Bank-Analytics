
-- 4. Historical GDP ranking by year

CREATE OR REPLACE VIEW marts.vw_country_ranking AS

SELECT
    c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    f.value AS gdp_usd,

    RANK() OVER (
        PARTITION BY f.year
        ORDER BY f.value DESC
    ) AS gdp_rank,

    DENSE_RANK() OVER (
        PARTITION BY f.year
        ORDER BY f.value DESC
    ) AS dense_gdp_rank

FROM warehouse.fact_indicators f

JOIN warehouse.dim_countries c
    ON c.country_id = f.country_id

WHERE f.indicator_code = 'NY.GDP.MKTP.CD'
  AND f.value IS NOT NULL
  AND c.is_aggregate = FALSE;
