# APEX Dashboard و Command Bar - مواصفات الواجهة

**الإصدار:** 1.0
**التاريخ:** January 30, 2026
**الحالة:** Ready for Development

---

## 1. نظرة عامة على الواجهة

يتكون تطبيق Atlas من صفحتين رئيسيتين:

| الصفحة | الوصف | الأولويات |
|---|---|---|
| **Dashboard (الصفحة 1)** | لوحة التحكم الرئيسية تعرض ملخص البيانات والتنبيهات | عرض البيانات الفورية، التنبيهات، الرسوم البيانية |
| **Command Bar (الصفحة 2)** | شريط الأوامر للتفاعل مع النظام باللغة الطبيعية | معالجة الأوامر بالعربية والإنجليزية، تنفيذ الاستعلامات |

---

## 2. لوحة التحكم (Dashboard - Page 1)

### 2.1 تخطيط الصفحة

```
┌─────────────────────────────────────────────────────────────┐
│                    ATLAS Dashboard                          │
│  [Language Toggle: عربي | English]  [User: ATLAS_ADMIN]   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐ │
│  │ Total Employees  │  │ Active POs       │  │ Unpaid    │ │
│  │      1,245       │  │      89          │  │ Invoices  │ │
│  │    [Chart]       │  │    [Chart]       │  │     34    │ │
│  └──────────────────┘  └──────────────────┘  └───────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ System Alerts & Notifications                        │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ ⚠️  5 Overdue Invoices - Total: 45,000 SAR          │   │
│  │ ⚠️  3 Employees with Pending Approvals              │   │
│  │ ✓  All Purchase Orders on Track                     │   │
│  │ ℹ️  Weekly Sync Completed Successfully              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Recent Transactions                                  │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ [Table with latest records]                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Go to Command Bar]                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 مكونات الصفحة

#### 2.2.1 رؤوس البطاقات (KPI Cards)
```sql
-- SQL Query for KPI Cards
SELECT 
    (SELECT COUNT(*) FROM ATLAS_EMPLOYEES WHERE ASSIGNMENT_STATUS = 'ACTIVE') AS TOTAL_EMPLOYEES,
    (SELECT COUNT(*) FROM ATLAS_PURCHASE_ORDERS WHERE STATUS = 'OPEN') AS ACTIVE_POS,
    (SELECT COUNT(*) FROM ATLAS_AP_INVOICES WHERE PAYMENT_STATUS = 'UNPAID' AND DUE_DATE < SYSDATE) AS OVERDUE_INVOICES,
    (SELECT SUM(INVOICE_AMOUNT) FROM ATLAS_AP_INVOICES WHERE PAYMENT_STATUS = 'UNPAID' AND DUE_DATE < SYSDATE) AS OVERDUE_AMOUNT
FROM DUAL;
```

#### 2.2.2 التنبيهات (Alerts Region)
```sql
-- SQL Query for Alerts
SELECT 
    ALERT_ID,
    ALERT_TYPE,
    ALERT_MESSAGE,
    SEVERITY_LEVEL,
    CREATED_DATE
FROM ATLAS_ALERTS
WHERE ALERT_STATUS = 'ACTIVE'
ORDER BY SEVERITY_LEVEL DESC, CREATED_DATE DESC
FETCH FIRST 10 ROWS ONLY;
```

#### 2.2.3 الجدول (Recent Transactions)
```sql
-- SQL Query for Recent Transactions
SELECT 
    'Employee' AS RECORD_TYPE,
    FULL_NAME AS RECORD_NAME,
    LAST_SYNC_DATE AS LAST_UPDATED
FROM ATLAS_EMPLOYEES
UNION ALL
SELECT 
    'Invoice' AS RECORD_TYPE,
    INVOICE_NUMBER AS RECORD_NAME,
    LAST_SYNC_DATE AS LAST_UPDATED
FROM ATLAS_AP_INVOICES
UNION ALL
SELECT 
    'PO' AS RECORD_TYPE,
    PO_NUMBER AS RECORD_NAME,
    LAST_SYNC_DATE AS LAST_UPDATED
FROM ATLAS_PURCHASE_ORDERS
ORDER BY LAST_UPDATED DESC
FETCH FIRST 20 ROWS ONLY;
```

---

## 3. شريط الأوامر (Command Bar - Page 2)

### 3.1 تخطيط الصفحة

```
┌─────────────────────────────────────────────────────────────┐
│                    ATLAS Command Bar                        │
│  [Language Toggle: عربي | English]  [User: ATLAS_ADMIN]   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Enter your command (English or Arabic):              │   │
│  │ ┌────────────────────────────────────────────────┐   │   │
│  │ │ [Text Input - p_command]                       │   │   │
│  │ │                                                 │   │   │
│  │ └────────────────────────────────────────────────┘   │   │
│  │ [Submit] [Clear] [Help]                              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Processing... (Hidden until response)                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Response / Results                                   │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ [Dynamic region - shows results based on response]   │   │
│  │                                                      │   │
│  │ - Query Results (if SELECT)                         │   │
│  │ - Error Message (if invalid)                        │   │
│  │ - Help Text (if help requested)                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Command History                                      │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ [List of previous commands]                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Back to Dashboard]                                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 مكونات الصفحة

#### 3.2.1 منطقة الإدخال (Command Input Region)
- **نوع المكون:** Text Input
- **الحد الأقصى للأحرف:** 1000
- **الحقول المطلوبة:** p_command
- **الزر:** Submit (يستدعي عملية معالجة)

#### 3.2.2 منطقة المعالجة (Processing Region)
- **نوع المكون:** Static Content
- **الحالة:** Hidden initially
- **الرسالة:** "جاري المعالجة... يرجى الانتظار" / "Processing... Please wait"

#### 3.2.3 منطقة النتائج (Results Region)
- **نوع المكون:** Dynamic Content (يتغير حسب نوع الرد)
- **الخيارات:**
  - **Query Results:** جدول يعرض نتائج الاستعلام
  - **Error Message:** رسالة خطأ بصيغة واضحة
  - **Help Text:** قائمة الأوامر المتاحة

#### 3.2.4 منطقة السجل (Command History Region)
```sql
-- SQL Query for Command History
SELECT 
    COMMAND_ID,
    COMMAND_TEXT,
    CREATED_DATE,
    EXECUTION_TIME
FROM ATLAS_COMMAND_HISTORY
WHERE USER_ID = :APP_USER
ORDER BY CREATED_DATE DESC
FETCH FIRST 50 ROWS ONLY;
```

---

## 4. العمليات (Processes)

### 4.1 عملية معالجة الأمر (Process: PROCESS_COMMAND)

```sql
-- Process: PROCESS_COMMAND
DECLARE
    l_response      CLOB;
    l_command       VARCHAR2(1000) := :P2_COMMAND;
    l_user_id       VARCHAR2(100) := :APP_USER;
BEGIN
    -- Call the command processor function
    l_response := ATLAS_PROCESS_COMMAND_V2(
        p_command   => l_command,
        p_user_id   => l_user_id,
        p_use_genai => 'Y'  -- Enable OCI GenAI
    );
    
    -- Store the response in a page item for display
    :P2_RESPONSE := l_response;
    
    -- Log the command in history
    INSERT INTO ATLAS_COMMAND_HISTORY (
        COMMAND_ID, USER_ID, COMMAND_TEXT, RESPONSE_TEXT, CREATED_DATE
    ) VALUES (
        SEQ_ATLAS_COMMANDS.NEXTVAL,
        l_user_id,
        l_command,
        l_response,
        SYSTIMESTAMP
    );
    COMMIT;
    
EXCEPTION
    WHEN OTHERS THEN
        :P2_RESPONSE := '{"type":"error","message":"' || SQLERRM || '"}';
END;
```

---

## 5. الدعم اللغوي (Bilingual Support)

### 5.1 تبديل اللغة (Language Toggle)
- **الخيارات:** عربي | English
- **التأثير:** تغيير جميع التسميات والرسائل في الصفحة
- **التخزين:** في متغير الجلسة (Session State)

### 5.2 الرسائل بلغتين
| الإنجليزية | العربية |
|---|---|
| Total Employees | إجمالي الموظفين |
| Active Purchase Orders | طلبيات الشراء النشطة |
| Unpaid Invoices | الفواتير غير المدفوعة |
| Enter your command | أدخل أمرك |
| Processing... | جاري المعالجة... |
| Submit | إرسال |
| Help | مساعدة |

---

## 6. معايير الأمان

- ✅ جميع الاستعلامات تمر عبر `ATLAS_VALIDATE_QUERY`
- ✅ لا يمكن تنفيذ أوامر DDL/DML
- ✅ جميع الأوامر تُسجل في `ATLAS_AUDIT_LOG`
- ✅ التحقق من صلاحيات المستخدم

---

## 7. خطوات التنفيذ

1. إنشاء الصفحات في APEX
2. إضافة المناطق (Regions) والعناصر (Items)
3. إنشاء العمليات (Processes)
4. إضافة الأزرار والأحداث
5. تطبيق الأنماط (Styling)
6. الاختبار الشامل
