-- =============================================================================
-- dim_date: one row per calendar day, 2016-01-01 to 2018-12-31.
-- Full calendar years with no gaps, as Power BI time intelligence
-- (SAMEPERIODLASTYEAR, DATEADD) requires. Month names are built with CASE
-- instead of a vendor-specific format function, so the view stays portable.
-- =============================================================================
CREATE OR REPLACE VIEW dim_date AS
WITH days AS (
    SELECT CAST(generate_series AS DATE) AS date
    FROM generate_series(TIMESTAMP '2016-01-01', TIMESTAMP '2018-12-31', INTERVAL 1 DAY)
)
SELECT date,
       CAST(EXTRACT(YEAR    FROM date) AS INTEGER)                          AS year,
       CAST(EXTRACT(QUARTER FROM date) AS INTEGER)                          AS quarter,
       'Q' || CAST(EXTRACT(QUARTER FROM date) AS VARCHAR)                   AS quarter_label,
       CAST(EXTRACT(MONTH   FROM date) AS INTEGER)                          AS month_number,
       CASE CAST(EXTRACT(MONTH FROM date) AS INTEGER)
           WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Apr'
           WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug'
           WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dec'
       END                                                                  AS month_name,
       CAST(DATE_TRUNC('month', date) AS DATE)                              AS month_start,
       CAST(EXTRACT(YEAR FROM date) AS VARCHAR) || '-'
         || LPAD(CAST(EXTRACT(MONTH FROM date) AS VARCHAR), 2, '0')        AS year_month,
       CAST(EXTRACT(YEAR FROM date) * 100 + EXTRACT(MONTH FROM date) AS INTEGER) AS year_month_key,
       CAST(EXTRACT(DOW FROM date) AS INTEGER)                              AS day_of_week,  -- 0 = Sunday
       CASE CAST(EXTRACT(DOW FROM date) AS INTEGER)
           WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed'
           WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' ELSE 'Sat'
       END                                                                  AS day_name,
       CASE WHEN EXTRACT(DOW FROM date) IN (0, 6) THEN 1 ELSE 0 END         AS is_weekend,
       -- 1 inside Jan 2017 to Aug 2018, the complete months used for trends.
       CASE WHEN date BETWEEN DATE '2017-01-01' AND DATE '2018-08-31'
            THEN 1 ELSE 0 END                                               AS in_analysis_window
FROM days;
