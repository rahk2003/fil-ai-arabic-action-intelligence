# Demo Scenarios

1. **New task:** `ارسلي التقرير بكرة الساعة 9 الصباح` with a supplied creation timestamp. Show extracted evidence and normalized Riyadh timestamp.
2. **Missing context:** analyze the same message without a timestamp. Show preserved text and uncertainty instead of an invented date.
3. **Multiple actions:** `تأجل الاجتماع للخميس، ولا تنسون ترسلون التقرير قبل الأربعاء.` Show two action objects.
4. **Scope update:** enter `حلل كل البيانات` then `خلاص حلل بس جزء`. Confirm the first task, show `update_task_scope`, the missing detail, and save the follow-up to the same task history only after review.
5. **Reschedule and calendar:** create `اجتماع المشروع` on October 18, reschedule it to October 22, then show one task ID with the old red marker and current green marker.
6. **Model comparison:** run `عندي طلب بسيط: اكتبي مقدمة عربية للمبادرة` through both real models. Point out the raw predictions separately from the extracted action and the contamination warning on the saved reference.
7. **File import:** download a CSV/XLSX template, preview validation/duplicates, and confirm only valid rows.
8. **Persistence:** refresh the browser and reopen the same task history.
9. **Known limitation:** `اكملي التسجيل قبل الساعة التاسعة مساء` demonstrates the deadline/reschedule baseline error.
10. **Evaluation:** separate the original 24-row baseline, reported Colab 125-row comparison, contaminated repository diagnostic, and tiny semantic-pair evaluation.
