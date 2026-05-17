MESSAGES = {
    "en": {
        "welcome": "Welcome to the tournament! Let's get you registered.",
        "startgg_prompt": "First, please link your Start.gg account by clicking the button below.",
        "startgg_linked": "✅ Start.gg account linked successfully! GamerTag: **{gamer_tag}**",
        "lang_prompt": "Please choose your preferred language for tournament notifications:\n1. Arabic (العربية)\n2. English",
        "cfn_prompt": "Thanks! Now, please enter your **CFN ID** (Capcom Fighter Network ID).",
        "avatar_prompt": "Got it! Finally, please upload an image to use as your **Avatar** (min 100x100px).",
        "safety_check": "⏳ Analyzing image for safety and quality...",
        "reg_complete": "✅ Registration complete! Your profile is ready. Welcome to the tournament.",
        "profile_update": "You are already registered! Would you like to update your profile?",
        "error_generic": "❌ Something went wrong. Please try again or contact an admin.",
        "error_safety": "❌ Image rejected: {reason}",
        "error_quality": "❌ Image too small or invalid format.",
        "timeout": "⏰ Registration session expired. Please click the Register button again.",
    },
    "ar": {
        "welcome": "مرحباً بك في البطولة! لنبدأ عملية التسجيل.",
        "startgg_prompt": "أولاً، يرجى ربط حساب Start.gg الخاص بك عن طريق الضغط على الزر أدناه.",
        "startgg_linked": "✅ تم ربط حساب Start.gg بنجاح! GamerTag: **{gamer_tag}**",
        "lang_prompt": "يرجى اختيار لغتك المفضلة لتنبيهات البطولة:\n1. العربية\n2. الإنجليزية",
        "cfn_prompt": "شكراً! الآن، يرجى إدخال معرف **CFN ID** الخاص بك.",
        "avatar_prompt": "ممتاز! أخيراً، يرجى رفع صورة لاستخدامها كصورة رمزية (Avatar) (بحد أدنى 100x100 بكسل).",
        "safety_check": "⏳ يتم الآن تحليل الصورة للتأكد من سلامتها وجودتها...",
        "reg_complete": "✅ اكتمل التسجيل! ملفك الشخصي جاهز الآن. أهلاً بك في البطولة.",
        "profile_update": "أنت مسجل بالفعل! هل تود تحديث ملفك الشخصي؟",
        "error_generic": "❌ حدث خطأ ما. يرجى المحاولة مرة أخرى أو التواصل مع المدير.",
        "error_safety": "❌ تم رفض الصورة: {reason}",
        "error_quality": "❌ الصورة صغيرة جداً أو صيغتها غير مدعومة.",
        "timeout": "⏰ انتهت مهلة جلسة التسجيل. يرجى الضغط على زر التسجيل مرة أخرى.",
    }
}

def get_msg(key: str, lang: str = "en", **kwargs) -> str:
    return MESSAGES.get(lang, MESSAGES["en"]).get(key, "").format(**kwargs)
