# مخطط عرض FI'L AI | فِعل

1. **المشكلة الواقعية:** الرسائل العربية تحمل مهام وتغييرات مبعثرة يصعب تتبعها.
2. **الحل:** تحويل الرسالة إلى Intent + Actions + Date/Time + Evidence مع Human Confirmation.
3. **البيانات:** 96 رسالة اصطناعية للخط الأساسي، و500 اصطناعية لضبط CAMeLBERT، وMASSIVE ar-SA للاستكشاف فقط، و0 مراجعة بشرية داخل المجال.
4. **NLP Architecture:** تصنيف خام، استخراج بالقواعد، تفسير فعل سياقي، MiniLM embeddings مع fallback لفظي، تأكيد، ثم SQLite history.
5. **Baseline:** Accuracy 50% وMacro-F1 0.494 على 24 مثالًا اصطناعيًا فقط.
6. **Model improvement:** مقارنة Word/Character TF-IDF وLR/SVM؛ لم يتحسن الاختبار، لذلك لم تتم الترقية.
7. **Transformer — المقارنة الأساسية:** تجربة Colab مُبلّغ عنها على نفس 125 رسالة اصطناعية: Baseline 72.0% / Macro-F1 ≈0.719 مقابل CAMeLBERT 89.6% / ≈0.895، أي +17.6 نقطة مئوية في الدقة. ليست دقة واقعية، ولم تُحفظ تنبؤات الصفوف لإعادة إنتاجها محليًا.
8. **تحذير تسرب البيانات:** نتيجة 95.8% على 24 رسالة متداخلة مع بيانات الضبط تشخيص تكامل فقط، وليست مقارنة علمية مستقلة.
9. **Error analysis:** Negation scope، Deadline vs Reschedule، Informational time mentions.
10. **Live demo:** Message Analyzer، Multiple actions، Conversation suggestion، confirmed local task.
11. **الحدود والخطوة القادمة:** ملف الـ500 وتقسيم عائلات إعادة الصياغة غير متاحين للتدقيق؛ الخطوة التالية جمع بيانات واقعية منزوعة الهوية، Double annotation، Locked test set، ثم Fine-tuning مضبوط.
