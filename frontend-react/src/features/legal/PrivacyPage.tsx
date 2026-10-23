import { Link } from 'react-router-dom';
import aiTobLogo from '@/assets/aitob-logo.svg';

export function PrivacyPage() {
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
            <Link to="/terms" className="text-gray-400 hover:text-white transition-colors">شروط الخدمة (Terms)</Link>
            <Link to="/login" className="px-3.5 py-1.5 rounded-lg bg-accentYellow text-black font-bold hover:bg-yellow-400 transition-colors">
              تسجيل الدخول
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12 leading-relaxed">
        <div className="border-b border-white/10 pb-6 mb-8">
          <div className="inline-block px-2.5 py-1 rounded bg-cyan-400/10 border border-cyan-400/20 text-cyan-300 text-xs font-mono font-bold uppercase tracking-wider mb-3">
            Privacy Policy · سياسة الخصوصية
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">سياسة الخصوصية وحماية البيانات</h1>
          <p className="mt-2 text-sm text-gray-400">
            تاريخ السريان: 23 أكتوبر 2026 · الرابط الرسمي: <a href="https://aitob.bashtech.xyz/privacy" className="text-cyan-400 hover:underline">https://aitob.bashtech.xyz/privacy</a>
          </p>
        </div>

        <div className="space-y-8 text-sm text-gray-300">
          {/* Section 1 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-cyan-400">1.</span> مقدمة (Overview)
            </h2>
            <p>
              نحن في <strong>aiTOB</strong> نلتزم بأعلى معايير الشفافية والمسؤولية في التعامل مع بيانات المستخدمين ومنظمي البطولات واللاعبين. تهدف هذه السياسة إلى توضيح نوع البيانات التي نجمعها، وأسباب جمعها، وكيفية حمايتها وحقوقك في حذفها.
            </p>
          </section>

          {/* Section 2 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-cyan-400">2.</span> البيانات التي نقوم بجمعها (Data We Collect)
            </h2>
            <ul className="list-disc list-inside space-y-2.5">
              <li>
                <strong>بيانات الحساب:</strong> عنوان البريد الإلكتروني للمنظم، والاسم المعروض، وسجلات الدخول المشفرة.
              </li>
              <li>
                <strong>بيانات منصة Discord:</strong> المعرف الرقمي للمستخدم (Discord User ID)، ومعرف السيرفر (Guild ID)، ومعرف القنوات المخصصة لنداءات المباريات. لا نقوم إطلاقاً بقراءة أو تخزين الرسائل الخاصة (DMs) أو محادثات السيرفر غير المتعلقة بتنظيم البطولة.
              </li>
              <li>
                <strong>بيانات البطولة واللاعبين:</strong> ألقاب اللاعبين التنافسية (Gamertags)، أسماء الشخصيات المختارة، وصور الملف الشخصي (Avatars) المقدمة للبث المباشر وبطاقات النتائج.
              </li>
              <li>
                <strong>ملفات تعريف الارتباط الفنية (Cookies):</strong> استخدام ملفات <code>HttpOnly</code> المشفرة للمحافظة على أمان الجلسة ومنع اختراق الحسابات، دون أي ملفات تتبع إعلانية للطرف الثالث.
              </li>
            </ul>
          </section>

          {/* Section 3 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-cyan-400">3.</span> كيفية استخدام البيانات (How We Use Data)
            </h2>
            <p className="mb-2">تُستخدم البيانات حصرياً لتقديم الخدمات التنافسية التالية:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-300">
              <li>عرض بيانات المباريات في شاشات البث المباشر (OBS Overlays) في الوقت الحقيقي.</li>
              <li>إرسال إشعارات استدعاء اللاعبين للمحطات عبر قنوات الديسكورد المحددة من المنظم.</li>
              <li>توليد بوسترات التتويج والمراكز الثمانية الأولى (Top 8 / Results Media).</li>
            </ul>
          </section>

          {/* Section 4 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-cyan-400">4.</span> مشاركة البيانات مع مزودي الخدمة (Third Parties)
            </h2>
            <p className="mb-2">نحن لا نبيع أو نؤجر أي بيانات للمعلنين. تتم مشاركة البيانات مع:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-300">
              <li><strong>Discord:</strong> لتنفيذ عمليات البوت والتحقق من صلاحيات المشرفين.</li>
              <li><strong>Start.gg و Challonge:</strong> لمزامنة جداول ومجموعات البطولة وتحديث النتائج الرسمية.</li>
              <li><strong>OpenAI / Google:</strong> فقط عند تفعيلك للمساعد الذكي وبالمفاتيح الخاصة بك.</li>
            </ul>
          </section>

          {/* Section 5 */}
          <section className="bg-cardDark/50 border border-white/5 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-3">
              <span className="text-cyan-400">5.</span> حقوق المستخدم وحذف البيانات (Your Rights & Data Deletion)
            </h2>
            <p className="mb-3">
              وفقاً للوائح حماية البيانات العالمية وسياسات مطوري منصة Discord:
            </p>
            <div className="bg-black/20 border border-white/5 rounded-lg p-3 text-xs leading-relaxed space-y-2">
              <p>
                يحق لأي لاعب أو منظم طلب الاطلاع على البيانات المحفوظة، أو طلب إزالة صورته، أو حذف كافة بيانات حسابه نهائياً (Right to Erasure).
              </p>
              <p>
                لتقديم طلب حذف، تواصل معنا عبر البريد: <a href="mailto:privacy@bashtech.xyz" className="text-cyan-400 font-bold hover:underline">privacy@bashtech.xyz</a> وسيتم معالجة الطلب في غضون 48 ساعة.
              </p>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs text-gray-500">
          <p>© 2026 aiTOB. جميع الحقوق محفوظة.</p>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:text-white transition-colors">شروط الخدمة</Link>
            <a href="mailto:privacy@bashtech.xyz" className="hover:text-white transition-colors">privacy@bashtech.xyz</a>
          </div>
        </div>
      </main>
    </div>
  );
}
