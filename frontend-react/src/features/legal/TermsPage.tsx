import { Link } from 'react-router-dom';
import aiTobLogo from '@/assets/aitob-logo.svg';

export function TermsPage() {
  return (
    <div className="min-h-screen bg-appDark text-gray-200 font-sans selection:bg-accentYellow selection:text-black">
      {/* Header */}
      <header className="border-b border-white/10 bg-cardDark/80 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <img src={aiTobLogo} alt="aiTOB" className="w-8 h-8 group-hover:scale-105 transition-transform" />
            <span className="font-bold text-white tracking-wider text-base font-rajdhani">aiTOB</span>
          </Link>
          <div className="flex items-center gap-4 text-xs font-semibold">
            <Link to="/privacy" className="text-gray-400 hover:text-white transition-colors">سياسة الخصوصية (Privacy)</Link>
            <Link to="/login" className="px-3.5 py-1.5 rounded-lg bg-accentYellow text-black font-bold hover:bg-yellow-400 transition-colors">
              تسجيل الدخول
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12 leading-relaxed">
        <div className="border-b border-white/10 pb-6 mb-8">
          <div className="inline-block px-2.5 py-1 rounded bg-amber-400/10 border border-amber-400/20 text-amber-300 text-xs font-mono font-bold uppercase tracking-wider mb-3">
            Legal Agreement · شروط الخدمة
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">شروط خدمة واستخدام منصة aiTOB</h1>
          <p className="mt-2 text-sm text-gray-400">
            تاريخ السريان: 23 أكتوبر 2026 · الموقع الرسمي: <a href="https://aitob.bashtech.xyz" className="text-accentYellow hover:underline">https://aitob.bashtech.xyz</a>
          </p>
        </div>

        <div className="space-y-8 text-sm text-gray-300">
          {/* Section 1 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">1.</span> التعريف بالخدمة (Service Definition)
            </h2>
            <p>
              منصة <strong>aiTOB (AI Tournament Organizer Bot)</strong> هي نظام تشغيلي وبرمجي متكامل مخصص لأتمتة مسابقات الألعاب الإلكترونية، وإدارة جداول المواجهات، وربط البث المباشر (OBS Studio)، وتوليد صور النتائج التنافسية (Top8er Graphics).
              باستخدامك للمنصة، فإنك تقر وتوافق على الالتزام بكافة الشروط المذكورة هنا.
            </p>
          </section>

          {/* Section 2 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">2.</span> مسؤوليات منظم البطولة (Tournament Organizers)
            </h2>
            <ul className="list-disc list-inside space-y-2">
              <li>منظم البطولة هو المسؤول الحصري عن إدارة فعالياته وفض النزاعات التحكيمية وقبول نتائج اللاعبين. المنصة توفر أدوات تقنية تشغيلية ولا تتدخل في النتائج الرسمية للبطولات.</li>
              <li>يلتزم المنظم بأخذ موافقة صريحة من اللاعبين المشاركين على استخدام أسمائهم، وألقابهم (Gamertags)، وصورهم في شاشات البث المباشر وبوسترات النتائج الإحصائية.</li>
            </ul>
          </section>

          {/* Section 3 - BYOC */}
          <section className="bg-gradient-to-br from-cardDark/80 via-cardDark to-amber-500/5 border border-amber-500/20 rounded-xl p-6">
            <div className="flex items-center gap-2 text-amber-300 font-bold text-xs uppercase tracking-wider mb-1">
              <span>⚠️</span> مهم جداً
            </div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-amber-400">3.</span> سياسة المفاتيح الخاصة (BYOC - Bring Your Own Credential)
            </h2>
            <p className="mb-3">
              تعتمد المنصة مبدأ <strong>BYOC</strong>، حيث يقوم كل منظم أو مؤسسة بإدخال مفاتيح الاعتماد والـ API الخاصة به لمنصات الطرف الثالث (مثل: Start.gg, Challonge, OpenAI, Google Gemini).
            </p>
            <ul className="list-disc list-inside space-y-2 text-gray-300">
              <li>يتحمل المنظم المسؤولية الكاملة عن كافة الاستهلاكات المالية أو الفواتير المفروضة من مزودي الذكاء الاصطناعي أو منصات البطولات.</li>
              <li>تلتزم aiTOB بتشفير هذه المفاتيح بمفاتيح رئيسية (Master Encryption Keys) داخل قاعدة البيانات وعدم مشاركتها إطلاقاً بين مساحات العمل.</li>
            </ul>
          </section>

          {/* Section 4 - AI */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">4.</span> إخلاء مسؤولية الذكاء الاصطناعي (AI Disclaimer)
            </h2>
            <p>
              جميع اقتراحات الذكاء الاصطناعي ومساعد البطولة الآلي هي <strong>اقتراحات إرشادية واستشارية فقط</strong>. لا تتحمل المنصة مسؤولية أي خطأ في قراءة القوانين أو تصنيف اللاعبين، والقرار النهائي والملزم يعود للمحكم البشري للبطولة.
            </p>
          </section>

          {/* Section 5 - Game IP */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">5.</span> الملكية الفكرية وعلامات الألعاب التجارية (Game IP)
            </h2>
            <p>
              أسماء الألعاب (مثل Street Fighter و Tekken) وصور الشخصيات والعلامات التجارية لشركات الألعاب (مثل Capcom و Bandai Namco) هي ملك لأصحابها الشرعيين. استخدامها داخل قوالب النتائج هو استخدام عادل لأغراض تنظيمية وتوثيقية تنافسية تخدم مجتمعات اللاعبين (Community Fan-Content).
            </p>
          </section>

          {/* Section 6 - Station Agent */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">6.</span> برنامج المحطة وسياسة اللعب النظيف (Station Agent EULA)
            </h2>
            <p className="mb-2">
              برنامج المحطة (Station Agent) وملحقات التيليمتري مصممة حصراً للبطولات والمباريات المحلية (Offline Local Tournaments).
            </p>
            <p className="text-red-300/90 text-xs">
              ⛔ يحظر تماماً استخدام برامج ومودات التيليمتري في مباريات الأونلاين التنافسية العامة (Ranked Online Matchmaking)، وتخلي المنصة مسؤوليتها عن أي حظر لحساب لاعب نتيجة استخدام المود في غير سياقه التنافسي المعتمد.
            </p>
          </section>

          {/* Section 7 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-accentYellow">7.</span> حدود المسؤولية (Limitation of Liability)
            </h2>
            <p>
              تُقدم المنصة "كما هي" دون ضمانات بعدم انقطاع الخدمة بسبب مشاكل في شبكة الإنترنت أو خوادم الطرف الثالث (Discord, Start.gg). ولا تتحمل المنصة مسؤولية أي خسائر غير مباشرة ناتجة عن تعطل بث أو تأخر مباراة.
            </p>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs text-gray-500">
          <p>© 2026 aiTOB. جميع الحقوق محفوظة.</p>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-white transition-colors">سياسة الخصوصية</Link>
            <a href="mailto:legal@bashtech.xyz" className="hover:text-white transition-colors">legal@bashtech.xyz</a>
          </div>
        </div>
      </main>
    </div>
  );
}
