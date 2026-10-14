# مخطط عرض FI'L AI | فِعل

1. **المشكلة الواقعية:** الرسائل العربية تحمل مهام وتغييرات مبعثرة يصعب تتبعها.
2. **الحل:** تحويل الرسالة إلى Intent + Actions + Date/Time + Evidence مع Human Confirmation.
3. **البيانات:** 96 رسالة اصطناعية للخط الأساسي، و500 اصطناعية لضبط CAMeLBERT، وMASSIVE ar-SA للاستكشاف فقط، و0 مراجعة بشرية داخل المجال.
4. **NLP Architecture:** تصنيف خام، استخراج بالقواعد، تفسير فعل سياقي، MiniLM embeddings مع fallback لفظي، تأكيد، ثم SQLite history.
5. **Baseline:** Accuracy 50% وMacro-F1 0.494 على 24 مثالًا اصطناعيًا فقط.
6. **Model improvement:** مقارنة Word/Character TF-IDF وLR/SVM؛ لم يتحسن الاختبار، لذلك لم تتم الترقية.
7. **Transformer:** CAMeLBERT-DA مضبوط دقيقًا؛ مقارنة Colab على 125 اصطناعية (72.0% مقابل 89.6%)، وتشخيص 24 المتداخل ليس دليلًا مستقلًا.
8. **Error analysis:** Negation scope، Deadline vs Reschedule، Informational time mentions.
9. **Live demo:** Message Analyzer، Multiple actions، Conversation suggestion، confirmed local task.
10. **الحدود والخطوة القادمة:** جمع بيانات واقعية منزوعة الهوية، Double annotation، Locked test set، ثم Fine-tuning مضبوط.
