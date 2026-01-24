{{
    config(
        materialized='table',
        tags=['intermediate']
    )
}}

WITH news AS (
    SELECT *
    FROM {{ ref('stg_news')}}
),

final AS (
    SELECT
        extraction_date,
        mentioned_ticker,
        SUM(CASE WHEN ticker_sentiment_label = 'Bullish' THEN 1 ELSE 0 END) AS bullish_count,
        SUM(CASE WHEN ticker_sentiment_label = 'Bearish' THEN 1 ELSE 0 END) AS bearish_count,
        SUM(CASE WHEN ticker_sentiment_label = 'Neutral' THEN 1 ELSE 0 END) AS neutral_count,
        SUM(CASE WHEN ticker_sentiment_label = 'Somewhat-Bullish' THEN 1 ELSE 0 END) AS somewhat_bullish_count,
        SUM(CASE WHEN ticker_sentiment_label = 'Somewhat-Bearish' THEN 1 ELSE 0 END) AS somewhat_bearish_count,
        ROUND(AVG(ticker_sentiment_score)::numeric, 2) AS avg_sentiment_score
    FROM news 
    WHERE mentioned_ticker IS NOT NULL
    GROUP BY extraction_date, mentioned_ticker
)

SELECT * FROM final