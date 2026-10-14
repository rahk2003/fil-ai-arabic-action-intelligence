# Amazon MASSIVE ar-SA Dataset Exploration

## Verified source

- Official repository: https://huggingface.co/datasets/AmazonScience/massive
- Locale: `ar-SA`; license: **CC BY 4.0**
- Rows: train 11,514, validation/dev 2,033, test 2,974; total 16,521
- Original split membership, scenario, intent, utterance, and slot annotations are preserved.

MASSIVE contains localized single-shot virtual-assistant utterances across 60 intents and 18 scenarios. It is not a corpus of real workplace messages and its labels must not be silently converted into FI'L AI's four intents.

## Schema

`id, locale, partition, scenario, intent, utt, annot_utt, worker_id, slot_method, judgments, source_split`

## Quality checks

- Unique scenarios: 18; unique intents: 60
- Normalized duplicate groups: 537; rows involved: 1545
- Rows with explicit date/time slot annotations: 3,180

| Column | Missing |
| --- | ---: |
| id | 0 |
| locale | 0 |
| partition | 0 |
| scenario | 0 |
| intent | 0 |
| utt | 0 |
| annot_utt | 0 |
| worker_id | 0 |
| slot_method | 0 |
| judgments | 0 |
| source_split | 0 |

## Representative samples

| Split | Utterance | Scenario | Original intent |
| --- | --- | --- | --- |
| train | صحيني تسعة الصباح يوم الجمعة | alarm | alarm_set |
| train | olly هدوء | audio | audio_volume_mute |
| train | اجعل الإضاءة أكثر دفء بقليل هنا | iot | iot_hue_lightchange |
| train | وقت النوم | iot | iot_hue_lightoff |
| train | olly اخفت النور في المجلس | iot | iot_hue_lightdim |
| train | olly نظف الشقة | iot | iot_cleaning |
| train | شيك متى يبدا العرض | calendar | calendar_query |
| train | أبغى اسمع أغنية محمد عبده مرة ثانية | play | play_music |
| train | توكد لي من أن سيارتي جاهزة | general | general_quirky |
| train | ما الأخبار | general | general_greet |
| train | قل لي الوقت في الرياض | datetime | datetime_query |
| train | قل لي الوقت في توقيت السعودية | datetime | datetime_convert |
| train | توصيل صيني | takeaway | takeaway_query |
| train | وقف منبه سبعة الصبح | alarm | alarm_remove |
| train | تكفى سوي قائمة بالمنبهات الشغالة | alarm | alarm_query |
| train | إيش أخبار كرة القدم اليوم | news | news_query |
| train | أنا أحب موسيقى الروك | music | music_likeness |
| train | مين مؤالف الموسيقى الحالية | music | music_query |
| train | خل الإضاءة أقوى | iot | iot_hue_lightup |
| train | اطلب مقلوبة للعشا | takeaway | takeaway_order |

The date/time spans are directly useful for extraction research. Scheduling/reminder examples are only annotation candidates for FI'L AI; supervised four-label use requires human review.
