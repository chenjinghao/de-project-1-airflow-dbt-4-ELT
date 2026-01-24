{{config(
    materialized='incremental',
    tags=['mart']
)}}

WITH price_extraction_date AS (
    SELECT *
    FROM {{ ref('stg_most_active_stocks') }}
    {% if is_incremental() %}
    WHERE date > (SELECT max(date) FROM {{ this }})
    {% endif %}
),

price_aggregated AS (
    SELECT 
        *
    FROM {{ ref('int_price') }}
),

news_sentiment AS (
    SELECT 
        *
    FROM {{ ref('int_news__analysis') }}
),

price_combined AS (
    SELECT 
        *
    FROM 
        price_extraction_date ped
    LEFT JOIN 
        price_aggregated pa
        ON ped.date = pa.extraction_date
        AND ped.ticker = pa.symbol
),

price_final AS (
    SELECT 
        date,
        ticker,
        price,
        volume,
        change_amount,
        change_percentage,
        rn,
        avg_close_price_past_100days,
        max_price_past_100days,
        min_price_past_100days,
        avg_volume_past_100days,
        max_volume_past_100days,
        min_volume_past_100days,
        CASE 
            WHEN price > avg_close_price_past_100days
            THEN 'Above Average 100 Days price'
            ELSE 'Below Average 100 Days price'
        END AS price_vs_100days_avg,
        CASE 
            WHEN volume > avg_volume_past_100days
            THEN 'Above Average 100 Days volume'
            ELSE 'Below Average 100 Days volume'
        END AS volume_vs_100days_avg
    FROM price_combined
),

final AS (
    SELECT 
        pf.*,
        ns.bullish_count,
        ns.bearish_count,
        ns.neutral_count,
        ns.somewhat_bullish_count,
        ns.somewhat_bearish_count,
        ns.avg_sentiment_score
    FROM 
        price_final pf
    LEFT JOIN 
        news_sentiment ns
        ON pf.date = ns.extraction_date
        AND pf.ticker = ns.mentioned_ticker
)

SELECT * FROM final