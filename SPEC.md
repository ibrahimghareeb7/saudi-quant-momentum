# Saudi Quant Momentum - SPEC

## الهدف

بناء نظام كمي تدريجي لسوق الاسهم السعودي، يبدأ ببايبلاين بيانات يومية نظيفة قبل اضافة اي مؤشرات او استراتيجية او تنبيهات.

## نطاق النسخة الاولى

هذه النسخة مخصصة للبيانات فقط:

- تحميل بيانات EOD اليومية.
- تخزين بيانات OHLCV.
- قراءة adjusted close من مزود البيانات اذا توفرت.
- حساب traded value.
- تصدير CSV نظيف وقابل للاستخدام في المراحل التالية.

خارج النطاق حاليا:

- لا Dashboard.
- لا AI.
- لا Telegram.
- لا Backtest.
- لا Portfolio construction.
- لا اشارات تداول.

## الاسهم التجريبية الاولى

| Ticker | الاسم |
| --- | --- |
| 1120.SR | الراجحي |
| 2222.SR | ارامكو |
| 7010.SR | STC |
| 1180.SR | الاهلي |
| 2010.SR | سابك |
| 1211.SR | معادن |
| 1150.SR | الانماء |
| 2380.SR | بترو رابغ |
| 7203.SR | علم |
| 2082.SR | اكوا باور |

## ملف الخرج الاول

الهدف العملي الاول هو ملف:

```text
prices.csv
```

بالاعمدة التالية، بهذا الترتيب:

```text
date, ticker, open, high, low, close, volume, traded_value
```

## قواعد تنظيف البيانات

- التاريخ بصيغة `YYYY-MM-DD`.
- التشغيل الافتراضي يستبعد اليوم الجاري كحد نهاية حصري لتفادي ادخال شمعة يومية غير مكتملة.
- رمز السهم كما هو في Yahoo Finance بصيغة `.SR`.
- الاعمدة السعرية ارقام عشرية.
- `volume` رقم صحيح عند توفره.
- `traded_value = close * volume`.
- حذف الصفوف التي لا تحتوي على بيانات OHLCV مكتملة.
- ترتيب البيانات حسب `date` ثم `ticker`.

## بوابة جودة البيانات

قبل اضافة اي Momentum او Ranking او Backtest يجب تشغيل:

```text
python main.py data-quality
```

المخرجات:

```text
data_quality_report.csv
suspicious_price_moves.csv
```

القواعد:

- لا يتم تعديل `prices.csv`.
- فحص `open/high/low/close <= 0`.
- فحص `high < low`.
- فحص خروج `open` عن نطاق `high-low`.
- فحص خروج `close` عن نطاق `high-low`.
- فحص تكرار `date+ticker`.
- فحص القيم المفقودة.
- فحص العائد اليومي الاعلى من `+15%` او الاقل من `-15%`.
- تلخيص عدد ايام التداول لكل سهم.
- تلخيص اول واخر تاريخ لكل سهم.

## بوابة تعديل الاسعار والاحداث الرأسمالية

نتائج جودة البيانات الحالية تعني ان المصدر غير صالح للـ Backtest كما هو بسبب خلط محتمل بين الاسعار المعدلة وغير المعدلة.

قبل اي Momentum او Ranking او Backtest يجب تشغيل:

```text
python main.py adjustment-audit
```

المخرجات:

```text
adjustment_audit_report.csv
ticker_quality_summary.csv
```

القواعد:

- لا يتم تعديل `prices.csv`.
- لا يتم تنظيف او استبدال اي ملف خرج موجود.
- فحص تجمعات العوائد اليومية التي تتجاوز `+/-15%`.
- تجميع الحركات المشبوهة اذا حدثت ضمن 5 جلسات تداول.
- الاشتباه في مشكلة تعديل سعري اذا انعكست حركة كبيرة خلال 1 الى 3 جلسات.
- مبدئيا لا تستخدم فترة `2010-2013` في اي Backtest حتى يثبت العكس.

## نسخة V2 بعد 2014

المصدر الحالي لا يصلح كمرجع تاريخي كامل للـ Backtest الجاد. لذلك يتم بناء نسخة ثانية بقص زمني فقط:

```text
start_date = 2014-01-01
```

التشغيل:

```text
python main.py v2-post-2014
```

المخرجات:

```text
prices_v2.csv
data_quality_report_v2.csv
suspicious_price_moves_v2.csv
adjustment_audit_report_v2.csv
ticker_quality_summary_v2.csv
sma200_v2.csv
```

القواعد:

- لا يتم تعديل `prices.csv`.
- لا يتم تنظيف القفزات يدويا.
- القص الزمني فقط مقبول.
- التعديل اليدوي للاسعار ممنوع لانه يصنع بيانات مزيفة.
- اذا بقي اكثر من 10-15 حركة مشبوهة بعد 2014 فنحتاج مصدر بيانات افضل.
- اذا اختفت اغلب المشاكل يمكن استخدام 2014-2026 كبداية مؤقتة للنسخة الاولى.

## استراتيجية V1 المؤقتة

المصدر المعتمد مؤقتا للنسخة الاولى:

```text
prices_v2.csv
```

يمنع استخدام `prices.csv` في اي Backtest.

الطبقة الاولى المسموحة:

```text
python main.py strategy-v2
```

المخرجات:

```text
liquidity_v2.csv
momentum_ranking_v2.csv
```

قواعد السيولة:

- `traded_value = close * volume`.
- `avg_traded_value_20d` هو متوسط 20 جلسة لقيمة التداول.
- `liquid = avg_traded_value_20d >= 20_000_000`.

قواعد الزخم:

- `rs_63d = close / close.shift(63) - 1`.
- `rs_126d = close / close.shift(126) - 1`.
- `volume_expansion = volume / rolling 20-day average volume`.
- `distance_52w_high = close / rolling 252-day high close - 1`.
- حساب percentile ranks مقطعية حسب التاريخ.
- `score = 0.40*rs_126d_rank + 0.30*rs_63d_rank + 0.20*volume_expansion_rank + 0.10*distance_52w_high_rank`.
- الترتيب تنازلي حسب `score` لكل تاريخ.
- يتم ترتيب الاسهم السائلة فقط.
- لا Backtest قبل مراجعة ranking يدويا.

مخرجات مراجعة الترتيب:

```text
python main.py ranking-review-v2
```

```text
top3_review_v2.csv
ranking_stability_v2.csv
```

`top3_review_v2.csv`:

```text
date, rank_1_ticker, rank_2_ticker, rank_3_ticker
```

`ranking_stability_v2.csv`:

```text
ticker, days_in_top3, days_in_top5, days_in_top10, first_top3_date, last_top3_date
```

الهدف من المراجعة هو معرفة هل النظام يطارد سهما واحدا بسبب خلل، ام يلتقط Momentum حقيقي.

## Risk-On / Risk-Off V2

هذا فلتر نظام سوق مؤقت، وليس TASI الحقيقي. يتم بناء TASI proxy من عوائد الاسهم العشرة المتاحة فقط.

التشغيل:

```text
python main.py regime-v2
```

المدخلات:

```text
prices_v2.csv
sma200_v2.csv
```

المخرجات:

```text
tasi_proxy_v2.csv
breadth_v2.csv
regime_v2.csv
```

القواعد:

- استخدام العائد اليومي المتساوي الوزن للاسهم المتاحة كـ TASI proxy مؤقت.
- بناء `tasi_proxy_close` من التراكم اليومي لمتوسط العوائد.
- حساب `tasi_proxy_sma200`.
- `above_tasi_sma200 = tasi_proxy_close > tasi_proxy_sma200`.
- `breadth` هي نسبة الاسهم فوق SMA200 الخاص بها حسب التاريخ من `sma200_v2.csv`.
- Risk-On اذا:
  - `above_tasi_sma200 == True`
  - و `breadth > 0.55`
- غير ذلك Risk-Off.
- لا يتم اضافة buffer في هذه المرحلة.
- لا Backtest قبل مراجعة regime.

اعمدة `regime_v2.csv`:

```text
date, tasi_proxy_close, tasi_proxy_sma200, above_tasi_sma200, breadth, regime_valid, regime
```

فترة بداية SMA200 للـ TASI proxy لا تحسب Risk-Off. يتم تعليمها كالتالي:

```text
regime_valid = False
regime = REGIME_UNAVAILABLE
```

Known limitation:

```text
Regime may flip frequently because breadth threshold is sharp and breadth moves in discrete 0.1 steps.
No hysteresis/buffer was added by design.
```

## المراحل التالية بعد نجاح البيانات

بعد تثبيت ملف الاسعار، يتم تنفيذ العناصر بالتدرج:

- SMA200: يتم تصديره في ملف مستقل باسم `sma200.csv`.
- Relative Strength 3M / 6M.
- Liquidity Filter.
- Risk-On / Risk-Off.

## ملف SMA200

ملف الخرج:

```text
sma200.csv
```

بالاعمدة التالية:

```text
date, ticker, close, sma200, above_sma200
```

قواعد الحساب:

- الحساب يتم لكل سهم على حدة حسب ترتيب التاريخ.
- `sma200` هو متوسط اغلاق اخر 200 جلسة.
- لا تظهر الصفوف الا بعد اكتمال 200 جلسة للسهم.
- `above_sma200` يساوي 1 اذا كان الاغلاق اعلى من SMA200، و0 خلاف ذلك.
