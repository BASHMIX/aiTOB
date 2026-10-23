# aiTOB Station Agent & Telemetry Bridge (SF6 + OBS Studio)

إضافة وتطبيق سطح مكتب رسمي تابع لمنصة **aiTOB** يربط محطة اللعب الحقيقية (Street Fighter 6) بمحطة البث (OBS Studio) وسيرفر المنصة المركزي.

---

## 🌟 الميزات الرئيسية (Features)

1. **الاستماع المباشر لبيانات اللعبة (UDP Telemetry Listener):**
   * يستمع على المنفذ المحلي `8080` (127.0.0.1) لاستقبال حزم سريعة وخفيفة من اللعبة بدون أي تأثير على معدل الإطارات (60fps).
   * يعرض في الوقت الحقيقي: نقاط الحياة (HP)، شريط الـ Drive Gauge، طاقة الـ Super Art، جولات الفوز، وحالة القتال.

2. **التحكم التلقائي في مشاهد OBS (Scene Automation):**
   * يتصل ببرنامج OBS Studio عبر بروتوكول `obs-websocket` v5 (المنفذ 4455).
   * تبديل المشاهد تلقائياً بناءً على أحداث المباراة:
     * `CHARACTER_SELECT` ➔ مشهد ما قبل المباراة (Versus Screen)
     * `FIGHTING` ➔ مشهد القتال المباشر (Gameplay)
     * `MATCH_OVER` ➔ مشهد إعلان الفائز (Victory Screen)

3. **المزامنة مع منصة aiTOB:**
   * استقبال أسماء اللاعبين والنتيجة من السيرفر تلقائياً عبر WebSocket.
   * خيار **الاعتماد التلقائي (Auto-Confirm)**: بمجرد انتهاء الطقم، يتم إرسال النتيجة إلى `api/active-matches/{set_id}/send` مباشرة لتحديث مسار البطولة والـ Overlays.

4. **وضع المحاكاة المدمج (Built-in Simulator):**
   * أزرار محاكاة لاختبار نقص الـ HP، الكو، وتبديل المشاهد فورياً حتى في حال عدم تشغيل اللعبة.

---

## 📁 هيكلية المجلد (Plugin Structure)

```text
plugins/station-agent/
├── sf6_mod_files/         # سكريبت REFramework اللعبة (aitob_telemetry.lua)
│   ├── aitob_telemetry.lua
│   └── README.md
├── electron/              # محرك Electron و UDP Listener
│   ├── main.ts            # خادم UDP 8080 وإدارة النوافذ والـ IPC
│   └── preload.ts         # جسر الأمان Context Bridge
├── src/                   # واجهة React ولوحة التحكم
│   ├── components/        # بطاقات اللاعبين، شريط التحكم، المودالز
│   ├── services/          # عملاء OBS WebSocket و aiTOB Bridge
│   ├── types/
│   ├── App.tsx
│   └── index.css
├── package.json
└── vite.config.ts
```

---

## 🚀 تشغيل التطبيق محلياً (Development)

قم بالدخول إلى مجلد الإضافة وتثبيت الحزم:
```powershell
Set-Location plugins/station-agent
npm install
npm run dev
```

---

## 📦 بناء ملف التوزيع والتحميل للمنصة (Building Downloadable Executable)

لبناء ملف الـ `.exe` القابل للتحميل والتوزيع للمنظمين من المنصة:
```powershell
npm run build
```
سيتم توليد ملفات الواجهة والـ Electron داخل `dist/` و `dist-electron/` تمهيداً لحزمها كملف `.exe` مستقل يمكن رفعه على منصة aiTOB في قسم تحميل أدوات المحطات.
