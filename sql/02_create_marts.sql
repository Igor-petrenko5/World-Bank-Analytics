--
-- PostgreSQL database dump
--

\restrict FViqTQQSZgGFfdeIJrFEX8KwsBP95jOrYyb2xUT1UJ5aZtfuhGRCZN9uNatLrA7

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: marts; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS marts;


--
-- Name: vw_country_ranking; Type: VIEW; Schema: marts; Owner: -
--

CREATE VIEW marts.vw_country_ranking AS
 SELECT c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    f.value AS gdp_usd,
    rank() OVER (PARTITION BY f.year ORDER BY f.value DESC) AS gdp_rank,
    dense_rank() OVER (PARTITION BY f.year ORDER BY f.value DESC) AS dense_gdp_rank
   FROM (warehouse.fact_indicators f
     JOIN warehouse.dim_countries c ON (((c.country_id)::text = (f.country_id)::text)))
  WHERE (((f.indicator_code)::text = 'NY.GDP.MKTP.CD'::text) AND (f.value IS NOT NULL) AND (c.is_aggregate = false));


--
-- Name: vw_gdp_dynamics; Type: VIEW; Schema: marts; Owner: -
--

CREATE VIEW marts.vw_gdp_dynamics AS
 SELECT c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    f.value AS gdp_usd,
    g.value AS gdp_growth_pct
   FROM ((warehouse.fact_indicators f
     JOIN warehouse.dim_countries c ON (((c.country_id)::text = (f.country_id)::text)))
     LEFT JOIN warehouse.fact_indicators g ON ((((g.country_id)::text = (f.country_id)::text) AND (g.year = f.year) AND ((g.indicator_code)::text = 'NY.GDP.MKTP.KD.ZG'::text) AND (g.source_id = f.source_id))))
  WHERE (((f.indicator_code)::text = 'NY.GDP.MKTP.CD'::text) AND (c.is_aggregate = false));


--
-- Name: vw_gdp_growth; Type: VIEW; Schema: marts; Owner: -
--

CREATE VIEW marts.vw_gdp_growth AS
 SELECT c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    f.value AS gdp_growth_pct
   FROM (warehouse.fact_indicators f
     JOIN warehouse.dim_countries c ON (((c.country_id)::text = (f.country_id)::text)))
  WHERE (((f.indicator_code)::text = 'NY.GDP.MKTP.KD.ZG'::text) AND (c.is_aggregate = false));


--
-- Name: vw_gdp_per_capita; Type: VIEW; Schema: marts; Owner: -
--

CREATE VIEW marts.vw_gdp_per_capita AS
 SELECT c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    f.value AS gdp_per_capita_usd,
    p.value AS gdp_per_capita_ppp
   FROM ((warehouse.fact_indicators f
     JOIN warehouse.dim_countries c ON (((c.country_id)::text = (f.country_id)::text)))
     LEFT JOIN warehouse.fact_indicators p ON ((((p.country_id)::text = (f.country_id)::text) AND (p.year = f.year) AND ((p.indicator_code)::text = 'NY.GDP.PCAP.PP.KD'::text) AND (p.source_id = f.source_id))))
  WHERE (((f.indicator_code)::text = 'NY.GDP.PCAP.CD'::text) AND (c.is_aggregate = false));


--
-- Name: vw_macro_indicators; Type: VIEW; Schema: marts; Owner: -
--

CREATE VIEW marts.vw_macro_indicators AS
 SELECT c.country_id,
    c.country_name,
    c.region_name,
    c.income_level,
    f.year,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'NY.GDP.MKTP.CD'::text)) AS gdp_usd,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'NY.GDP.MKTP.KD.ZG'::text)) AS gdp_growth_pct,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'NY.GDP.PCAP.CD'::text)) AS gdp_per_capita_usd,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'FP.CPI.TOTL.ZG'::text)) AS inflation_pct,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SL.UEM.TOTL.ZS'::text)) AS unemployment_pct,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SL.UEM.1524.ZS'::text)) AS youth_unemployment_pct,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SP.POP.TOTL'::text)) AS population,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SP.DYN.LE00.IN'::text)) AS life_expectancy,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SH.XPD.CHEX.GD.ZS'::text)) AS health_expenditure_pct_gdp,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'SE.XPD.TOTL.GD.ZS'::text)) AS education_expenditure_pct_gdp,
    max(f.value) FILTER (WHERE ((f.indicator_code)::text = 'IT.NET.USER.ZS'::text)) AS internet_users_pct
   FROM (warehouse.fact_indicators f
     JOIN warehouse.dim_countries c ON (((c.country_id)::text = (f.country_id)::text)))
  WHERE (c.is_aggregate = false)
  GROUP BY c.country_id, c.country_name, c.region_name, c.income_level, f.year;


--
-- PostgreSQL database dump complete
--

\unrestrict FViqTQQSZgGFfdeIJrFEX8KwsBP95jOrYyb2xUT1UJ5aZtfuhGRCZN9uNatLrA7

