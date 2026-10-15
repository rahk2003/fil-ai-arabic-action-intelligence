# تقرير التسليم والتحقق النهائي — FI'L AI | فِعل

تاريخ التحقق: 14 أكتوبر 2026 — `Asia/Riyadh`  
المشروع المرجعي: `/Users/rana/Documents/Wesh_Alay_NLP_Starter`

## 1. الأسباب الجذرية للمشكلات الأصلية

1. كانت الواجهة تخلط بين **تصنيف النموذج الخام** و**الإجراء المستخرج بالقواعد**؛ لذلك كان ظهور «مهمة جديدة» في الاستخراج يوحي خطأً بأن النموذج الأساسي صنّفها بصورة صحيحة.
2. كانت اقتراحات قاعدة البيانات تعتمد مباشرة على فئة المصنف، حتى عند عدم وجود قرينة فعل أو تغيير صريحة.
3. لم تكن تغييرات النطاق والمتطلبات والأولوية ممثلة في طبقة مستقلة؛ كانت الفئات الأربع تُحمّل معاني لم يُدرّب عليها المصنف.
4. المطابقة السياقية اعتمدت على تشابه لفظي فقط، وفشلت مع الضمائر والمتابعات القصيرة مثل «خلاص خله مختصر».
5. كان غلاف embeddings موجودًا لكنه غير موصول بخط FastAPI أو واجهة المحادثة.
6. استخدم تنسيق `ar-SA` الافتراضي، الذي قد يعرض التاريخ الهجري؛ ولم يُفرض التقويم الميلادي.
7. كانت نتائج 24 و125 رسالة تُعرض دون فصل كافٍ، مع خطر تفسير 95.8% كقياس مستقل رغم التداخل مع بيانات الضبط.
8. لم تظهر مجموعة الـ500 رسالة في سجل البيانات، ولم توضّح الواجهة أن ملف صفوفها غير موجود محليًا.
9. لم يكن هناك استيراد CSV/XLSX مع معاينة وتحقق صفّي.
10. كشف التحقق المرئي خطأ regex: النمط `بس` كان يطابق جزءًا من كلمة «بسيط»؛ أُصلح بحدود كلمة وأضيف اختبار رجوع.

## 2. التحسينات المنفذة

- فصل خمس مراحل ظاهرة: التصنيف الخام، الاستخراج، التفسير السياقي، العملية المقترحة، والتنفيذ المؤكد.
- إضافة عمليات سياقية: `create_task`, `update_task_scope`, `update_task_requirement`, `update_task_priority`, `reschedule_task`, `cancel_task`, `mark_complete`, `add_instruction`, `no_action`, `needs_clarification`.
- منع إنشاء اقتراح قاعدة بيانات من فئة المصنف وحدها؛ يلزم دليل قواعد/سياق.
- ربط المتابعات القصيرة بالمهمة السابقة باستخدام دلالة محلية + لفظ + مصطلحات مشتركة + حداثة، مع تأكيد إلزامي.
- تحميل مخبأ وكسول لنموذج `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`، وfallback لفظي معلن عند الفشل.
- إكمال المحادثات زمنيًا مع قبل/بعد، الدليل، المهمة المرتبطة، التفاصيل الناقصة، تأكيد/تعديل/رفض/طلب توضيح.
- إكمال تقويم ميلادي شهر/أسبوع/يوم في الرياض، مع الأحمر للموعد القديم والأخضر للحالي على معرّف مهمة واحد.
- إكمال إنشاء المهمة اليدوي: الاسم، الوصف، التاريخ الميلادي، الوقت الاختياري، الأولوية، الحالة، والملاحظات.
- إضافة استيراد CSV/XLSX: قوالب، حد 2 MB و500 صف، رؤوس عربية/إنجليزية، معاينة، كشف تكرار، تحقق تاريخ/حالة/أولوية، وعدادات.
- إعادة تنظيم صفحات البيانات والتقييم والأخطاء واللغة العربية المحايدة.

## 3. حالات فعلية قبل/بعد

| الرسالة | Baseline الخام | CAMeLBERT الخام | العملية الآمنة الحالية |
|---|---|---|---|
| بكرة الدوام أون لاين | `reschedule` | `reschedule` | `no_action` دون سياق |
| تم اعتماد التقرير النهائي | `new_task` | `cancellation` | `no_action` دون مهمة مرتبطة |
| السلام عليكم لاحد يجي بكرة | `reschedule` | `reschedule` | `no_action`؛ لا تُنشأ مهمة حضور موجبة |
| ارسلي التقرير قبل الساعة التاسعة مساء | `new_task` | `new_task` | `create_task` بعد التأكيد |
| عندي طلب بسيط: اكتبي مقدمة عربية للمبادرة | `cancellation` | `new_task` | `create_task`؛ يظهر تعارض Baseline/استخراج |

الدرجات المعروضة raw softmax غير معايرة، ولا تعني احتمال صحة موثوقًا.

## 4. تحقق المحادثة

المثال `حلل كل البيانات` ثم `خلاص حلل بس جزء` يعمل الآن كما يلي:

- الرسالة الأولى: `create_task`.
- الرسالة الثانية: التصنيف الخام الفعلي `cancellation`، لكن التفسير السياقي `update_task_scope`.
- المهمة المرتبطة: نفس مهمة الرسالة الأولى.
- التفصيل الناقص: «تحديد الجزء المطلوب».
- لا يحدث تعديل تلقائي.
- عند التأكيد في المتصفح أُنشئت المهمة رقم 3 ثم أضيف حدث `edited` إلى المهمة نفسها، والدليل «خلاص حلل بس جزء».

اختُبرت أيضًا أزواج التقرير المختصر، فرع الرياض، إعادة جدولة الاجتماع، إلغاء إرسال التقرير، وإضافة اللغة الإنجليزية.

## 5. تحقق التقويم والتاريخ

أُنشئت مهمة تحقق محلية رقم 4 بعنوان «عرض SDAIA التجريبي» بموعد أصلي `2026-10-18T10:00:00+03:00`، ثم نُقلت إلى `2026-10-22T14:00:00+03:00`.

- ظهر 18 أكتوبر بعلامة `border-rose/bg-rose` كموعد قديم.
- ظهر 22 أكتوبر بعلامة `border-emerald/bg-emerald` كموعد حالي.
- العلامتان تحملان `task_id=4`؛ لا توجد مهمة مكررة.
- العنوان المعروض «أكتوبر ٢٠٢٦» ميلادي صريح باستخدام `ar-SA-u-ca-gregory`.
- سجل المهمة يحتفظ بسبب التغيير والدليل وتوقيت تسجيل الحدث منفصلًا عن موعد المهمة.

## 6. الإنشاء اليدوي والاستيراد

- الإنشاء اليدوي يعمل عبر FastAPI والواجهة ويتطلب مربع تأكيد.
- CSV: اختبار معاينة حقيقي بصف صالح وصف بتاريخ غير صالح، ثم commit للصف الصالح، ثم كشفه كمكرر في المعاينة التالية.
- XLSX: أُنشئ workbook فعلي داخل الاختبار وقرأه `openpyxl` بنجاح.
- تنزيل قالب CSV وقالب Excel ظاهر ومربوط بالـAPI.
- لا تُستبدل المهام الموجودة ولا تُستورد الصفوف المكررة بصمت.

## 7. النماذج والـembeddings

- Baseline: `tfidf-logreg:intent_baseline` على CPU.
- CAMeLBERT: `camelbert-da:FIL_AI_CAMeLBERT` من `models/FIL_AI_CAMeLBERT/` على MPS.
- `id2label`: `0=cancellation`, `1=info_only`, `2=new_task`, `3=reschedule`.
- Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` على MPS، بعد 384، مخبأ في `models/embedding_cache`.
- لا يحدث استبدال صامت عند فشل CAMeLBERT.
- لا تُعد embeddings مصنف نية مضبوطًا دقيقًا، ولا تدمج المهام بناءً على cosine وحده.

## 8. نتائج المطابقة الدلالية الفعلية

مجموعة صغيرة صريحة المصدر: 12 زوجًا اصطناعيًا/مشتقًا من أمثلة المستخدم؛ 4 تحقق و8 اختبار.

| الطريقة | Precision | Recall | F1 | False matches |
|---|---:|---:|---:|---:|
| لفظية | 1.000 | 0.250 | 0.400 | 0 |
| MiniLM دلالية | 0.500 | 0.500 | 0.500 | 2 |

عتبة embeddings المختارة على أربعة أزواج تحقق فقط كانت 0.30، وهي غير مستقرة. يستخدم التطبيق عتبة تشغيل أكثر تحفظًا (`0.55`) مع أدلة كيان/حداثة وتأكيد بشري.

## 9. سجل البيانات والتقييم العلمي

- 96 اصطناعية: النموذج الأساسي؛ 72 تطوير / 24 اختبار محفوظ.
- 500 اصطناعية: CAMeLBERT وتجربة baseline على تقسيم Colab؛ 300/75/125. ملف الصفوف غير موجود محليًا، لذلك لا يمكن تدقيق exact/near duplicates أو عائلات paraphrase.
- MASSIVE ar-SA: 16,521، ترخيص CC BY 4.0، 60 فئة أصلية، للاستكشاف فقط ولم تُستخدم لتدريب فئات FI'L AI الأربع.
- مراجعة بشرية داخل المجال: 0.

سياقات التقييم منفصلة:

1. Baseline الأصلي: Accuracy 50.0%، Macro-F1 0.494 على 24 اصطناعية.
2. **المقارنة الأساسية المبلّغ عنها:** Colab على نفس 125 الاصطناعية: classical baseline 72.0% / ~0.719، CAMeLBERT 89.6% / ~0.895؛ التحسن +17.6 نقطة مئوية في الدقة. لا توجد تنبؤات صفّية لإعادة إنتاجها محليًا، ولا تمثل دقة واقعية.
3. **تحذير تسرب بيانات:** تشخيص المستودع 24 أعطى CAMeLBERT 95.8% / 0.958، لكنه متداخل مع بيانات الضبط وغير مستقل، لذلك ليس النتيجة الأساسية.

ملف تنبؤات Colab ومصفوفة التباسه غير محفوظين؛ تعرض الواجهة Precision/Recall/Confusion Matrix كـ«غير محفوظ» بدل اختلاقها.

## 10. الاختبارات والتحقق

- Python/FastAPI: **39 passed، 1 xfailed**. تشمل النتيجة اختبار إنشاء SQLite من قاعدة فارغة والترقية إلى Alembic head. الـxfail هو فشل Baseline المعروف في deadline-vs-reschedule، ومحتفظ به كتتبع صريح.
- React/Vitest: **5 ملفات، 10 اختبارات ناجحة**.
- Production build: نجح؛ 2,191 module transformed.
- CAMeLBERT integration diagnostic: نجح على MPS؛ 24 صفًا، Accuracy 0.9583، Macro-F1 0.9580، مع تحذير صريح بأنه اختبار ملوث للتكامل فقط.
- Semantic API: أبلغ `method=embeddings`, `device=mps`, `dimension=384`.
- قاعدة البيانات: `PRAGMA integrity_check = ok`، ولا أخطاء foreign-key، ولا تكرار title+deadline في المهام.
- المتصفح الفعلي: تحقق من التقويم، الاستيراد، المحادثة، المقارنة، سجل الـ500، فصل التقييم، وصفحة أخطاء فيها 30 سجلًا ومرشحان.
- الخادمان يعملان من مسار `Documents` نفسه على 8000 و5173.

## 11. الملفات الرئيسية المتغيرة

- NLP: `src/fil_ai/extraction.py`, `context.py`, `interpretation.py`, `pipeline.py`, `semantic.py`.
- Backend: `backend/app/main.py`, `schemas.py`, `services.py`, `settings.py`، و`backend/tests/test_api.py`.
- Frontend: `Layout.tsx`, `types.ts`, `lib/api.ts` وصفحات Calendar, Tasks, Analyzer, Conversations, Overview, Evaluation, Dataset, ErrorAnalysis واختباراتها.
- Data/evaluation: `data/evaluation/saudi_challenge_set.csv`, `context_pair_benchmark.csv`, و`results/context_matching/`, `results/camelbert/`.
- Scripts: `evaluate_context_matching.py`, `evaluate_saudi_challenges.py`, `evaluate_camelbert_integration.py`.
- Docs: README وملفات architecture/api/dataset/model/methodology/demo/presentation وهذه الوثيقة وقائمة SDAIA.

## 12. أوامر التشغيل الدقيقة

```bash
cd /Users/rana/Documents/Wesh_Alay_NLP_Starter
source .venv312/bin/activate
python -m pip install -r backend/requirements.txt -r requirements-dev.txt -r requirements-embeddings.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

طرفية ثانية:

```bash
cd /Users/rana/Documents/Wesh_Alay_NLP_Starter/frontend
npm install
npm run dev
```

الاختبارات:

```bash
cd /Users/rana/Documents/Wesh_Alay_NLP_Starter
.venv312/bin/python -m pytest backend/tests tests -q
.venv312/bin/python scripts/evaluate_context_matching.py
.venv312/bin/python scripts/evaluate_camelbert_integration.py --device auto
cd frontend
npm test
npm run build
```

Gradio الاحتياطي:

```bash
cd /Users/rana/Documents/Wesh_Alay_NLP_Starter
.venv312/bin/python app.py
```

## 13. المتبقي قبل ادعاء الجاهزية العلمية الكاملة

- جمع اختبار حقيقي سعودي داخل المجال، بموافقة وطمس هوية ومراجعين مستقلين.
- توفير ملف الـ500 وتقسيمه لتدقيق عائلات paraphrase والتكرار.
- حفظ تنبؤات Colab الصفية ومصفوفة الالتباس إذا أريد عرض Precision/Recall موثقين.
- توسيع تقييم استخراج الكيانات/الوقت وتفسير الأفعال السياقية.
- معايرة الدرجات أو تطبيق abstention مضبوط على بيانات تحقق بشرية.

## 14. جاهزية GitHub

المشروع منشور في المستودع العام `https://github.com/rahk2003/fil-ai-arabic-action-intelligence` على الفرع `main`. حُفظ checkpoint الخاص بـCAMeLBERT باستخدام Git LFS، بينما بقيت `.env` وقاعدة SQLite والبيئات الافتراضية و`node_modules` ومخبأ embeddings خارج Git. يتطلب الاستنساخ الكامل تشغيل `git lfs install` ثم `git lfs pull` قبل بدء التطبيق.

ملاحظة حفظ البيانات: لم تُحذف السجلات القديمة. لذلك قد تبقى اقتراحات معلقة أُنشئت بالإصدار السابق الضعيف؛ الإصدار الجديد يمنع تكرارها، ويمكن مراجعتها ورفضها من الواجهة بدل حذفها من قاعدة البيانات.
