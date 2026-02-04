# دليل تفعيل Oracle Fusion

هذا الدليل يوضح كيفية تفعيل الربط بين نظام Atlas وبيئة Oracle Fusion الخاصة بك، مع التركيز على استخدام الاتصال الآمن بدون محفظة (Walletless TLS) الموصى به من Oracle.

## 1. تحديث بيانات اعتماد Oracle Fusion في APEX

لربط Atlas ببيئة Oracle Fusion، تحتاج إلى تحديث بيانات الاعتماد في APEX.

1.  **تسجيل الدخول إلى APEX:**
    *   **URL:** `https://G05FA28D854C5E8-ATLASDB.adb.me-riyadh-1.oraclecloudapps.com/ords/apex`
    *   **Workspace:** `ATLAS`
    *   **Username:** `ATLAS_ADMIN`
    *   **Password:** `AtlasAdmin#2026!`

2.  **الانتقال إلى Web Credentials:**
    *   من صفحة APEX الرئيسية، اذهب إلى **App Builder**.
    *   اختر تطبيق **Atlas**.
    *   من القائمة العلوية، اذهب إلى **Shared Components**.
    *   تحت **Security**, اختر **Web Credentials**.

3.  **تعديل بيانات اعتماد Fusion:**
    *   ابحث عن بيانات الاعتماد المسماة `FUSION_CREDENTIAL` (إذا كانت موجودة) أو قم بإنشاء واحدة جديدة.
    *   **Name:** `FUSION_CREDENTIAL`
    *   **Authentication Type:** `Basic Authentication`
    *   **Username:** أدخل اسم المستخدم الخاص بك في Oracle Fusion (الذي يملك صلاحيات الوصول لـ REST APIs).
    *   **Password:** أدخل كلمة المرور الخاصة بالمستخدم.
    *   **Save Changes**.

## 2. تحديث REST Data Source لـ Oracle Fusion

بعد تحديث بيانات الاعتماد، تحتاج إلى تحديث رابط بيئة Fusion.

1.  **الانتقال إلى REST Data Sources:**
    *   من **Shared Components**, تحت **Data Sources**, اختر **REST Data Sources**.

2.  **تعديل Fusion HCM Workers:**
    *   ابحث عن `FUSION_HCM_WORKERS`.
    *   **Base URL:** أدخل رابط بيئة Oracle Fusion الخاصة بك (مثال: `https://your-fusion-instance.fa.oraclecloud.com`).
    *   **Authentication:** تأكد أنها تستخدم `FUSION_CREDENTIAL`.
    *   **Save Changes**.

3.  **تعديل REST Data Sources الأخرى:** كرر الخطوة 2 لجميع REST Data Sources المتعلقة بـ Fusion (مثل `FUSION_AP_INVOICES`, `FUSION_PO_HEADERS`).

## 3. تفعيل الاتصال بدون محفظة (Walletless TLS) لقاعدة البيانات

لضمان استمرارية الاتصال الآمن والموصى به من Oracle، تأكد من أن تطبيق APEX يستخدم الاتصال بدون محفظة.

1.  **التحقق من إعدادات قاعدة البيانات:**
    *   هذا الإعداد يتم على مستوى الاتصال من APEX إلى قاعدة البيانات، وقد تم تكوينه تلقائياً ليكون Walletless TLS أثناء النشر.
    *   لا تحتاج إلى إجراء يدوي هنا، ولكن تأكد من أن `sqlnet.ora` في المحفظة التي تستخدمها التطبيقات الخارجية لا يزال يشير إلى الشهادات الصحيحة إذا كنت تستخدم mTLS.

## 4. تشغيل المزامنة الأولية

بعد تحديث جميع الإعدادات، يمكنك تشغيل المزامنة الأولية لسحب البيانات من Oracle Fusion.

1.  **الانتقال إلى SQL Workshop:**
    *   من APEX الرئيسية، اذهب إلى **SQL Workshop** ثم **SQL Commands**.

2.  **تشغيل إجراءات المزامنة:**
    *   قم بتنفيذ الإجراءات التالية واحداً تلو الآخر:
        ```sql
        EXEC ATLAS_SYNC_EMPLOYEES;
        EXEC ATLAS_SYNC_DEPARTMENTS;
        EXEC ATLAS_SYNC_LOCATIONS;
        EXEC ATLAS_SYNC_SUPPLIERS;
        EXEC ATLAS_SYNC_PURCHASE_ORDERS;
        EXEC ATLAS_SYNC_AP_INVOICES;
        COMMIT;
        ```

3.  **التحقق من البيانات:**
    *   يمكنك الآن التحقق من الجداول المحلية (مثل `ATLAS_EMPLOYEES`) للتأكد من أن البيانات قد تم سحبها بنجاح.

## 5. تفعيل التنبيهات الاستباقية

لتفعيل محرك الذكاء التشغيلي، قم بتشغيل إجراء التنبيهات:

1.  **في SQL Workshop:**
    ```sql
    EXEC ATLAS_INTELLIGENCE_PKG.GENERATE_PROACTIVE_ALERTS;
    COMMIT;
    ```

2.  **التحقق من التنبيهات:**
    ```sql
    SELECT * FROM ATLAS_ALERTS ORDER BY CREATED_DATE DESC;
    ```

بهذه الخطوات، يكون نظام Atlas متصلاً بـ Oracle Fusion، ومحرك الذكاء التشغيلي يعمل بكامل طاقته.
