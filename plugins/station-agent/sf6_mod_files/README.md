# aiTOB - ملفات مود Street Fighter 6 (REFramework Telemetry)

هذا المجلد يحتوي على سكريبت قراءة بيانات اللعبة الحية (Telemetry) وتمريرها عبر شبكة الـ UDP المحلية إلى تطبيق **aiTOB Station Agent**.

---

## متطلبات التثبيت (Installation Steps)

### 1. تثبيت REFramework:
1. اذهب إلى صفحة [REFramework GitHub Releases](https://github.com/praydog/REFramework/releases) أو الـ Nightly Builds.
2. قم بتحميل الملف المخصص لـ **Street Fighter 6** (ملف `SF6.zip`).
3. استخرج ملف `dinput8.dll` وضعه في المجلد الرئيسي للعبة:
   ```text
   C:\Program Files (x86)\Steam\steamapps\common\Street Fighter 6\dinput8.dll
   ```
4. شغّل اللعبة مرة واحدة فقط للوصول للقائمة الرئيسية، ثم أغلقها. ستلاحظ إنشاء مجلد جديد باسم `reframework`.

---

### 2. تثبيت مكتبة LuaSocket:
* قم بتحميل حزمة `REFramework LuaSocket`.
* ضع ملف `socket.lua` ومجلد `socket/` (الذي يحتوي على `core.dll`) داخل:
   ```text
   <SF6_Game_Path>\reframework\
   ```

---

### 3. تثبيت سكريبت aiTOB:
* انسخ ملف `aitob_telemetry.lua` من هذا المجلد وضعه داخل مجلد التشغيل التلقائي:
   ```text
   <SF6_Game_Path>\reframework\autorun\aitob_telemetry.lua
   ```

---

## كيف تتأكد من عمل السكريبت داخل اللعبة؟
1. شغل اللعبة.
2. اضغط زر **`Insert`** في لوحة المفاتيح لفتح قائمة REFramework الداخلية.
3. ستجد خياراً باسم **aiTOB Station Telemetry**.
4. اضغط عليه، ستشاهد حالة الاتصال وزر **`Send Test Telemetry Packet`**.
5. بمجرد فتح تطبيق **aiTOB Station Agent**، ستتحول العلامة إلى 🟢 Connected وسيبدأ بث نقاط الـ HP والشخصيات تلقائياً.
