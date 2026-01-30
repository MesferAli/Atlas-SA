# Atlas on OCI - خارطة الطريق للخطوات التالية

**الإصدار:** 1.0
**التاريخ:** January 30, 2026
**الحالة:** Ready for Next Phase Implementation

---

## 📋 ملخص الوضع الحالي

| المكون | الحالة | التفاصيل |
|---|---|---|
| **البنية التحتية** | ✅ مكتملة | Compartment, ATP, VCN, API Gateway في الرياض |
| **قاعدة البيانات** | ✅ مكتملة | 11 جدول، 5 تسلسل، نظام الأمان فعال |
| **RAG Pipeline** | ✅ مكتملة | 7 دوال/إجراءات، نظام التنبيهات الاستباقية |
| **APEX Workspace** | ✅ مكتملة | Workspace ATLAS، مستخدم ATLAS_ADMIN |
| **الواجهة (UI)** | 🔄 قيد التطوير | Dashboard و Command Bar جاهزة للتنفيذ |
| **OCI GenAI** | 🔄 قيد التكوين | بحاجة لتفعيل الأوراق الاعتمادية |
| **Fusion Integration** | 🔄 قيد التطوير | السكريبتات جاهزة، بحاجة لبيانات الاتصال |

---

## 🎯 الخطوات التالية (المرحلة الثانية)

### المرحلة 1: تصميم واجهة المستخدم (UI) - الأسبوع الأول

#### 1.1 بناء لوحة التحكم (Dashboard)
**الملفات المطلوبة:**
- ✅ `docs/apex_ui_specification.md` - المواصفات
- ✅ `apex/pages/page_001_dashboard.sql` - السكريبت

**الخطوات:**
1. قم بفتح APEX من خلال:
   ```
   https://G05FA28D854C5E8-ATLASDB.adb.me-riyadh-1.oraclecloudapps.com/ords/apex
   ```

2. سجل الدخول:
   - **Workspace:** ATLAS
   - **Username:** ATLAS_ADMIN
   - **Password:** AtlasAdmin#2026!

3. انسخ محتوى `page_001_dashboard.sql` والصقه في SQL Workshop

4. قم بتنفيذ السكريبت لإنشاء الصفحة

5. اختبر الصفحة وتحقق من ظهور البيانات

#### 1.2 بناء شريط الأوامر (Command Bar)
**الملفات المطلوبة:**
- ✅ `apex/pages/page_002_command_bar_full.sql` - السكريبت الكامل

**الخطوات:**
1. انسخ محتوى `page_002_command_bar_full.sql` والصقه في SQL Workshop

2. قم بتنفيذ السكريبت لإنشاء الصفحة

3. اختبر الصفحة بأوامر بسيطة:
   - "Show all employees"
   - "كم عدد الموظفين؟"

4. تحقق من تسجيل الأوامر في `ATLAS_COMMAND_HISTORY`

---

### المرحلة 2: تفعيل الذكاء الاصطناعي الكامل - الأسبوع الثاني

#### 2.1 تكوين OCI Generative AI
**المتطلبات:**
- مفتاح API لخدمة OCI Generative AI
- معرف المستخدم (User OCID)
- معرف التينانسي (Tenancy OCID)
- البصمة (Fingerprint)

**الخطوات:**
1. احصل على مفتاح API من OCI Console:
   - اذهب إلى **Identity → Users**
   - اختر المستخدم الخاص بك
   - اضغط **API Keys**
   - انسخ محتوى المفتاح الخاص

2. قم بتنفيذ السكريبت التالي في SQL Workshop:
   ```sql
   BEGIN
       APEX_CREDENTIAL.CREATE_CREDENTIAL(
           p_credential_name        => 'OCI_GENAI_CREDENTIAL',
           p_credential_static_id   => 'OCI_GENAI_CREDENTIAL',
           p_authentication_type    => APEX_CREDENTIAL.C_TYPE_OCI,
           p_oci_user_id            => 'ocid1.user.oc1..aaaaaaaa4xg4to5j35zym7px2se2ycsoe77bjso6ijkjzi2byv5i6olryc2a',
           p_oci_private_key        => '[PASTE_YOUR_PRIVATE_KEY_HERE]',
           p_oci_tenancy_id         => 'ocid1.tenancy.oc1..aaaaaaaabq6v27kpitaeu2bpvjqm6v6bkgyuoej2mp5irmtmih777ffohteq',
           p_oci_fingerprint        => '9e:aa:f6:96:1b:37:44:80:10:56:60:d4:6c:46:bc:d9'
       );
       COMMIT;
   END;
   ```

3. اختبر الاتصال بتنفيذ دالة GenAI:
   ```sql
   SELECT ATLAS_GENAI_NL_TO_SQL('Show all employees', 'TEST_USER') FROM DUAL;
   ```

#### 2.2 تفعيل دالة NL-to-SQL الكاملة
**الملفات المطلوبة:**
- ✅ السكريبت الذي تم توفيره سابقاً: `ATLAS_GENAI_NL_TO_SQL`

**الخطوات:**
1. تحقق من أن الدالة `ATLAS_GENAI_NL_TO_SQL` موجودة:
   ```sql
   SELECT object_name FROM user_objects 
   WHERE object_name = 'ATLAS_GENAI_NL_TO_SQL';
   ```

2. اختبر الدالة مع أوامر متنوعة:
   ```sql
   SELECT ATLAS_GENAI_NL_TO_SQL('List all unpaid invoices', 'TEST_USER') FROM DUAL;
   SELECT ATLAS_GENAI_NL_TO_SQL('عرض الموردين النشطين', 'TEST_USER') FROM DUAL;
   ```

---

### المرحلة 3: مزامنة البيانات مع Oracle Fusion - الأسبوع الثالث

#### 3.1 تكوين بيانات اتصال Fusion
**المتطلبات:**
- عنوان URL لنسخة Fusion الخاصة بك
- اسم المستخدم وكلمة المرور للمستخدم المتكامل
- معرفات الـ Modules المطلوبة

**الخطوات:**
1. قم بتحديث السكريبت `fusion_sync_integration.sql` بـ:
   - استبدل `your-fusion-instance.oracle.com` بـ URL الفعلي
   - استبدل `fusion_integration_user` و `YourFusionPassword123!` بالبيانات الفعلية

2. قم بتنفيذ السكريبت المحدث:
   ```sql
   @fusion_sync_integration.sql
   ```

#### 3.2 اختبار المزامنة
**الخطوات:**
1. قم بتنفيذ المزامنة اليدوية:
   ```sql
   EXEC ATLAS_SYNC_EMPLOYEES;
   EXEC ATLAS_SYNC_INVOICES;
   EXEC ATLAS_SYNC_PURCHASE_ORDERS;
   ```

2. تحقق من البيانات المزامنة:
   ```sql
   SELECT COUNT(*) FROM ATLAS_EMPLOYEES;
   SELECT COUNT(*) FROM ATLAS_AP_INVOICES;
   SELECT COUNT(*) FROM ATLAS_PURCHASE_ORDERS;
   ```

3. تحقق من سجلات المزامنة:
   ```sql
   SELECT * FROM ATLAS_AUDIT_LOG 
   WHERE EVENT_TYPE LIKE 'SYNC%' 
   ORDER BY CREATED_DATE DESC;
   ```

---

## 📊 جدول الزمن المقترح

| الأسبوع | المهام | الحالة |
|---|---|---|
| **الأسبوع 1** | بناء Dashboard و Command Bar | 🔄 قيد التطوير |
| **الأسبوع 2** | تفعيل OCI GenAI والاختبار | 🔄 قيد التطوير |
| **الأسبوع 3** | مزامنة Fusion والاختبار الشامل | ⏳ في الانتظار |
| **الأسبوع 4** | الاختبارات الأمنية والأداء | ⏳ في الانتظار |
| **الأسبوع 5** | النشر الإنتاجي والتوثيق النهائية | ⏳ في الانتظار |

---

## 🔐 متطلبات الأمان المهمة

قبل الانتقال إلى الإنتاج:

- [ ] تفعيل SSL/TLS على جميع الاتصالات
- [ ] تشفير جميع كلمات المرور في متغيرات البيئة
- [ ] تفعيل Multi-Factor Authentication (MFA)
- [ ] إعداد نسخ احتياطية يومية
- [ ] اختبار استرجاع البيانات من النسخ الاحتياطية
- [ ] تفعيل مراقبة الأداء والتنبيهات
- [ ] توثيق جميع العمليات الحساسة

---

## 📞 الدعم والمساعدة

إذا واجهت أي مشاكل:

1. **تحقق من السجلات:**
   ```sql
   SELECT * FROM ATLAS_AUDIT_LOG ORDER BY CREATED_DATE DESC;
   ```

2. **اختبر الاتصال بـ Fusion:**
   ```sql
   SELECT APEX_WEB_SERVICE.MAKE_REST_REQUEST(
       p_url => 'https://your-fusion-instance.oracle.com/hcmRestApi/latest/workers?limit=1',
       p_http_method => 'GET'
   ) FROM DUAL;
   ```

3. **تحقق من حالة الوظائف المجدولة:**
   ```sql
   SELECT job_name, enabled, next_run_date FROM user_scheduler_jobs;
   ```

---

## 📝 ملاحظات مهمة

- جميع الملفات موجودة في مستودع GitHub: `https://github.com/MesferAli/Atlas-OCI`
- تأكد من تحديث البيانات الحساسة قبل تنفيذ أي سكريبت
- اختبر جميع التغييرات في بيئة التطوير أولاً
- احتفظ بنسخة احتياطية من جميع البيانات قبل أي تغيير كبير
