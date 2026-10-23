import { useState } from 'react';

const ARABIC_WAIVER = `[إقرار وتفويض استخدام الصور والبث الإعلامي للبطولة]
بتسجيلي ومشاركتي في هذه البطولة، أوافق طواعية على البنود التالية:
1. التصوير والبث المباشر: أفوّض إدارة البطولة ومنصة aiTOB بتصوير وبث ومشاركة مجريات المباريات، بما في ذلك اسم اللاعب (GamerTag)، الاسم المستعار، والصور الشخصية المعتمَدة في لوائح الترتيب، وبطاقات نتائج المباريات (Result Cards)، وتصاميم أفضل 8 لاعبين (Top 8)، وعلى منصات البث المباشر (مثل Twitch و YouTube و Kick) وحسابات التواصل الاجتماعي التابعة للبطولة.
2. الحقوق غير الحصرية: أقر بأن هذه المواد والمقاطع تُستخدم لأغراض تنظيم وتغطية وأرشفة البطولة، دون أي مقابل مالي أو مطالبة بحقوق نشر لاحقة.
3. الالتزام بالروح الرياضية والنزاهة: أتعهد بالالتزام بقواعد اللعب النظيف وتوجيهات الحكام، وأدرك أن أي تلاعب أو سوء سلوك قد يؤدي إلى الإقصاء المباشر (DQ).`;

const ENGLISH_WAIVER = `[Tournament Media Consent & Broadcast Waiver]
By registering and participating in this tournament, I voluntarily agree to the following terms:
1. Photography, Livestreaming & Graphics: I hereby grant tournament organizers and the aiTOB platform the non-exclusive right to photograph, record, stream, and publish my gameplay, Gamertag/handle, and authorized headshot/avatar on tournament livestreams (Twitch, YouTube, Kick), overlay broadcasts, match result cards, and social media recaps (e.g., Top 8 brackets).
2. Media Usage & Promotion: I acknowledge that these graphics and recordings are used solely for tournament operation, media coverage, and historical archiving, without royalty or further compensation.
3. Fair Play & Conduct: I agree to uphold fair play and tournament code of conduct. Any manipulation or misconduct may result in immediate disqualification (DQ).`;

export function LegalSettingsSection() {
  const [copiedType, setCopiedType] = useState<'ar' | 'en' | null>(null);

  const copyToClipboard = async (text: string, type: 'ar' | 'en') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedType(type);
      setTimeout(() => setCopiedType(null), 2500);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopiedType(type);
      setTimeout(() => setCopiedType(null), 2500);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Platform Legal Documentation Cards */}
      <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <span>⚖️</span>
          <span>Legal Documentation & Public Policies</span>
        </h2>
        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-textDim">
          Official public policies governing aiTOB platform use, organizer responsibilities, data protection, and external integrations.
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <a
            href="/terms"
            target="_blank"
            rel="noopener noreferrer"
            className="group rounded-xl border border-white/10 bg-appDark/60 p-4 transition-all hover:border-accentYellow/50 hover:bg-white/[0.03]"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white group-hover:text-accentYellow">Terms of Service</span>
              <span className="text-xs text-textDim group-hover:text-accentYellow">↗</span>
            </div>
            <p className="mt-2 text-xs text-textDim leading-relaxed">
              Rules of use, organizer liability, BYOC credentials, fair use of game IP, and dispute resolution.
            </p>
          </a>

          <a
            href="/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="group rounded-xl border border-white/10 bg-appDark/60 p-4 transition-all hover:border-accentYellow/50 hover:bg-white/[0.03]"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white group-hover:text-accentYellow">Privacy Policy</span>
              <span className="text-xs text-textDim group-hover:text-accentYellow">↗</span>
            </div>
            <p className="mt-2 text-xs text-textDim leading-relaxed">
              Data handling, credential encryption, player privacy, cookie policy, and GDPR/CCPA data erasure requests.
            </p>
          </a>

          <a
            href="/terms#station-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="group rounded-xl border border-white/10 bg-appDark/60 p-4 transition-all hover:border-accentYellow/50 hover:bg-white/[0.03]"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white group-hover:text-accentYellow">Station Agent EULA</span>
              <span className="text-xs text-textDim group-hover:text-accentYellow">↗</span>
            </div>
            <p className="mt-2 text-xs text-textDim leading-relaxed">
              Desktop client software license for local tournament stations, offline caching, and hardware safety.
            </p>
          </a>
        </div>
      </section>

      {/* Organizer Player Media Waiver Template */}
      <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm space-y-4">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>📋</span>
              <span>قالب إقرار تسجيل اللاعبين وتفويض النشر الإعلامي (Player Media Waiver)</span>
            </h2>
            <span className="rounded-full border border-statusGreen/30 bg-statusGreen/10 px-2.5 py-0.5 text-[10px] font-bold text-statusGreen uppercase tracking-wider">
              موصى به للمنظمين
            </span>
          </div>
          <p className="mt-1 text-xs text-textDim leading-relaxed">
            يُنصح بإضافة هذا النص في صفحة تسجيل بطولتك على Start.gg أو Challonge أو في استمارة التسجيل المحلية، لضمان موافقة اللاعبين القانونية على عرض أسمائهم وصورهم في البث المباشر (OBS overlays) وتصاميم النتائج.
          </p>
        </div>

        {/* Arabic Template */}
        <div className="rounded-xl border border-white/10 bg-appDark/80 p-4 space-y-3" dir="rtl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-accentYellow">القالب العربي (للبطولات المحلية والإقليمية)</span>
            <button
              type="button"
              onClick={() => void copyToClipboard(ARABIC_WAIVER, 'ar')}
              className="rounded-lg bg-accentYellow px-3 py-1.5 text-xs font-bold text-black transition-transform active:scale-95 hover:bg-accentYellow/90"
            >
              {copiedType === 'ar' ? '✓ تم النسخ إلى الحافظة' : '📋 نسخ النص العربي'}
            </button>
          </div>
          <pre className="rounded-lg border border-white/5 bg-black/40 p-3 text-xs leading-relaxed text-zinc-300 font-sans whitespace-pre-wrap select-all">
            {ARABIC_WAIVER}
          </pre>
        </div>

        {/* English Template */}
        <div className="rounded-xl border border-white/10 bg-appDark/80 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-accentYellow">English Template (International Tournaments)</span>
            <button
              type="button"
              onClick={() => void copyToClipboard(ENGLISH_WAIVER, 'en')}
              className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-xs font-bold text-white transition-colors hover:bg-white/10 active:scale-95"
            >
              {copiedType === 'en' ? '✓ Copied to clipboard' : '📋 Copy English Text'}
            </button>
          </div>
          <pre className="rounded-lg border border-white/5 bg-black/40 p-3 text-xs leading-relaxed text-zinc-300 font-mono whitespace-pre-wrap select-all">
            {ENGLISH_WAIVER}
          </pre>
        </div>
      </section>

      {/* Compliance & BYOC Summary */}
      <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs text-amber-200/90 leading-relaxed space-y-2">
        <p className="font-bold text-amber-300 flex items-center gap-1.5">
          <span>⚠️</span>
          <span>إرشادات النزاهة والامتثال للمنظمين (Compliance Guidelines)</span>
        </p>
        <ul className="list-disc list-inside space-y-1 text-xs text-zinc-300">
          <li><strong>استقلالية النتائج:</strong> منصة Start.gg أو Challonge هي المرجع الرسمي المعتمد لتحديد الفائز وحالات الإقصاء (DQ). لا تتدخل aiTOB في تعديل أي نتيجة خارج صلاحيات المنظم الموثق.</li>
          <li><strong>حقوق الملكية الفكرية:</strong> أسماء الألعاب، الشعارات، والشخصيات هي ملك لشركاتها المطورة (مثل Capcom, Bandai Namco, Nintendo). يتم عرضها لأغراض التغطية التنافسية وفق مبدأ الاستخدام العادل (Fair Use).</li>
          <li><strong>مفاتيح المزودين (BYOC):</strong> يتحمل صاحب مساحة العمل المسؤولية الكاملة عن سرية واستهلاك المفاتيح الخاصة به (Discord Bot, Gemini, OpenAI, Start.gg).</li>
        </ul>
      </section>
    </div>
  );
}
