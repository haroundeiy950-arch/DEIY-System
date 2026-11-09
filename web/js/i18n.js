/* ==========================================================================
   DEIY translations: English (default), Somali and Arabic.
   The UI is rendered as plain HTML, so this module also walks the rendered
   tree and replaces exact English labels. Anything without a translation
   falls back to English, which keeps the app usable while translations grow.
   ========================================================================== */
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const STORAGE_KEY = "deiy.language";
  const SUPPORTED = ["en", "so", "ar"];
  const NAMES = { en: "English", so: "Soomaali", ar: "العربية" };

  const PHRASES = {
    so: {
      "Overview": "Guudmar",
      "Dashboard": "Shaxda",
      "Learning": "Waxbarasho",
      "Library": "Maktabadda",
      "Exams": "Imtixaannada",
      "Study rooms": "Qolalka waxbarashada",
      "Assignments": "Shaqooyinka",
      "Gradebook": "Buugga natiijooyinka",
      "Calendar": "Jadwalka",
      "Account": "Akoonka",
      "Notifications": "Ogeysiisyada",
      "Profile": "Astaanta",
      "Help & AI": "Caawimaad & AI",
      "Management": "Maamulka",
      "Content management": "Maamulka nuxurka",
      "Administration": "Maamulka guud",
      "Sign out": "Ka bax",
      "Need help?": "Caawimaad ma u baahan tahay?",
      "Apply now": "Hadda codso",
      "Ask the AI guide": "Weydii hagaha AI",
      "Sign in": "Gal",
      "To apply": "In la codsado",
      "AI application help": "Caawimaad codsi AI",
      "Your path from applicant to student": "Wadadaada laga bilaabo codsadaha ilaa ardayga",
      "Five short steps. The AI guide is beside you the whole way.":
        "Shan tallaabo oo gaaban. Hagaha AI ayaa kula socda wadada oo dhan.",
      "Application": "Codsi",
      "Join DEIY in three short steps": "Ku biir DEIY saddex tallaabo oo gaaban",
      "Your name & email": "Magacaaga & iimaylkaaga",
      "Photo & details": "Sawir & faahfaahin",
      "Password & review": "Furaha sirta & dib u eegis",
      "First name": "Magaca koowaad",
      "Second name": "Magaca labaad",
      "Third name": "Magaca saddexaad",
      "Family name": "Magaca qoyska",
      "Email address": "Cinwaanka iimaylka",
      "Date of birth": "Taariikhda dhalashada",
      "Country / residence": "Dal / degaan",
      "Program of study": "Barnaamijka waxbarashada",
      "Phone number": "Lambarka telefoonka",
      "Father's phone number": "Lambarka telefoonka aabbaha",
      "Nationality": "Jinsiyadda",
      "How will you sign in?": "Sidee u gali doontaa?",
      "Email and password": "Iimayl iyo fura sir",
      "Other provider": "Bixiye kale",
      "Preferred language": "Luqadda la doorbiday",
      "Create a password": "Samee furaha sirta",
      "Confirm password": "Xaqiiji furaha sirta",
      "Continue": "Sii wad",
      "Back": "Dib u noqo",
      "Review your details": "Dib u eeg faahfaahintaada",
      "Submit application": "Gudbi codsiga",
      "Already applied?": "Hore ma u codsatay?",
      "Verify your email": "Xaqiiji iimaylkaaga",
      "Choose your file": "Dooro faylkaaga",
      "Your photo": "Sawirkaaga",
      "A clear, front-facing photo. JPG, PNG or WebP, 5 MB maximum.":
        "Sawir cad oo wajiga ka muuqdo. JPG, PNG ama WebP, ugu badnaan 5 MB.",
      "Or paste an https image URL": "Ama dheji URL sawir https ah",
      "Start your application": "Bilow codsigaaga",
      "Read the full guide": "Akhri hagaha buuxa",
      "6-digit code": "Koodhka 6 lambar",
      "Verify email": "Xaqiiji iimaylka",
      "Resend code": "Dib u dir koodhka",
      "Go to sign in": "Tag gelitaanka",
      "Continue learning": "Sii wad waxbarashada",
      "Password": "Furaha sirta",
      "New here?": "Cusub ma tahay?",
      "Apply for an account": "Codso akoon",
      "Demo accounts": "Akoonnada tijaabada",
      "Application guide": "Hagaha codsiga",
      "How to apply, step by step": "Sida loo codsado, tallaabo tallaabo",
      "What you need": "Waxa aad u baahan tahay",
      "Good to know": "Wax wanaagsan in la ogaado",
      "Frequently asked questions": "Su'aalaha badanaa la weydiiyo",
      "Your profile": "Astaantaada",
      "Role": "Doorka",
      "Status": "Xaaladda",
      "Academic ID": "Aqoonsiga tacliinta",
      "Registration number": "Lambarka diiwaangelinta",
      "Country": "Dal",
      "Member since": "Xubin ilaa",
      "Applications": "Codsiyada",
      "Users & roles": "Isticmaalayaasha & doorarka",
      "Configuration": "Habaynta",
      "AI usage": "Isticmaalka AI",
      "Audit log": "Diiwaanka hubinta",
      "Save configuration": "Kaydi habaynta",
      "Refresh": "Cusboonaysii",
      "Approve": "Ansixi",
      "Reject": "Diid",
      "Details": "Faahfaahin",
      "Create staff account": "Samee akoon shaqaale",
      "Apply filters": "Codso shaandhaynta",
      "Edit": "Wax ka beddel",
      "Delete": "Tirtir",
      "Save": "Kaydi",
      "Cancel": "Jooji",
      "Program": "Barnaamij",
      "Preferred language": "Luqadda la doorbiday",
      "Sign-in provider": "Bixiyaha gelitaanka",
      "Email verified": "Iimayl la xaqiijiyay",
      "Not issued yet": "Weli lama bixin",
      "Edit user": "Wax ka beddel isticmaalaha",
      "Save changes": "Kaydi isbeddellada",
      "Delete user": "Tirtir isticmaalaha",
      "Edit your profile": "Wax ka beddel astaantaada",
      "Save profile": "Kaydi astaanta",
      "Change password": "Beddel furaha sirta",
      "Current password": "Furaha sirta hadda",
      "New password": "Furaha sirta cusub",
      "Confirm new password": "Xaqiiji furaha cusub",
      "Update password": "Cusboonaysii furaha sirta",
      "All roles": "Dhammaan doorarka",
      "All statuses": "Dhammaan xaaladaha"
    },
    ar: {
      "Overview": "نظرة عامة",
      "Dashboard": "لوحة التحكم",
      "Learning": "التعلم",
      "Library": "المكتبة",
      "Exams": "الامتحانات",
      "Study rooms": "غرف الدراسة",
      "Assignments": "الواجبات",
      "Gradebook": "سجل الدرجات",
      "Calendar": "التقويم",
      "Account": "الحساب",
      "Notifications": "الإشعارات",
      "Profile": "الملف الشخصي",
      "Help & AI": "المساعدة والذكاء الاصطناعي",
      "Management": "الإدارة",
      "Content management": "إدارة المحتوى",
      "Administration": "الإدارة العامة",
      "Sign out": "تسجيل الخروج",
      "Need help?": "هل تحتاج مساعدة؟",
      "Apply now": "قدّم الآن",
      "Ask the AI guide": "اسأل دليل الذكاء الاصطناعي",
      "Sign in": "تسجيل الدخول",
      "To apply": "للتقديم",
      "AI application help": "مساعدة التقديم بالذكاء الاصطناعي",
      "Your path from applicant to student": "مسارك من متقدم إلى طالب",
      "Five short steps. The AI guide is beside you the whole way.":
        "خمس خطوات قصيرة. دليل الذكاء الاصطناعي معك طوال الطريق.",
      "Application": "التقديم",
      "Join DEIY in three short steps": "انضم إلى DEIY في ثلاث خطوات قصيرة",
      "Your name & email": "اسمك وبريدك الإلكتروني",
      "Photo & details": "الصورة والتفاصيل",
      "Password & review": "كلمة المرور والمراجعة",
      "First name": "الاسم الأول",
      "Second name": "الاسم الثاني",
      "Third name": "الاسم الثالث",
      "Family name": "اسم العائلة",
      "Email address": "البريد الإلكتروني",
      "Date of birth": "تاريخ الميلاد",
      "Country / residence": "الدولة / محل الإقامة",
      "Program of study": "البرنامج الدراسي",
      "Phone number": "رقم الهاتف",
      "Father's phone number": "رقم هاتف الأب",
      "Nationality": "الجنسية",
      "How will you sign in?": "كيف ستسجل الدخول؟",
      "Email and password": "البريد الإلكتروني وكلمة المرور",
      "Other provider": "مزود آخر",
      "Preferred language": "اللغة المفضلة",
      "Create a password": "أنشئ كلمة مرور",
      "Confirm password": "تأكيد كلمة المرور",
      "Continue": "متابعة",
      "Back": "رجوع",
      "Review your details": "راجع تفاصيلك",
      "Submit application": "إرسال الطلب",
      "Already applied?": "هل قدّمت بالفعل؟",
      "Verify your email": "تحقق من بريدك الإلكتروني",
      "Choose your file": "اختر ملفك",
      "Your photo": "صورتك",
      "A clear, front-facing photo. JPG, PNG or WebP, 5 MB maximum.":
        "صورة واضحة للأمام. JPG أو PNG أو WebP، بحد أقصى 5 ميغابايت.",
      "Or paste an https image URL": "أو الصق رابط صورة https",
      "Start your application": "ابدأ تقديمك",
      "Read the full guide": "اقرأ الدليل الكامل",
      "6-digit code": "رمز من 6 أرقام",
      "Verify email": "تحقق من البريد",
      "Resend code": "إعادة إرسال الرمز",
      "Go to sign in": "اذهب لتسجيل الدخول",
      "Continue learning": "واصل التعلم",
      "Password": "كلمة المرور",
      "New here?": "جديد هنا؟",
      "Apply for an account": "قدّم للحصول على حساب",
      "Demo accounts": "حسابات تجريبية",
      "Application guide": "دليل التقديم",
      "How to apply, step by step": "كيفية التقديم خطوة بخطوة",
      "What you need": "ما تحتاجه",
      "Good to know": "معلومات مفيدة",
      "Frequently asked questions": "الأسئلة الشائعة",
      "Your profile": "ملفك الشخصي",
      "Role": "الدور",
      "Status": "الحالة",
      "Academic ID": "الرقم الأكاديمي",
      "Registration number": "رقم التسجيل",
      "Country": "الدولة",
      "Member since": "عضو منذ",
      "Applications": "الطلبات",
      "Users & roles": "المستخدمون والأدوار",
      "Configuration": "الإعدادات",
      "AI usage": "استخدام الذكاء الاصطناعي",
      "Audit log": "سجل التدقيق",
      "Save configuration": "حفظ الإعدادات",
      "Refresh": "تحديث",
      "Approve": "موافقة",
      "Reject": "رفض",
      "Details": "التفاصيل",
      "Create staff account": "إنشاء حساب موظف",
      "Apply filters": "تطبيق الفلاتر",
      "Edit": "تعديل",
      "Delete": "حذف",
      "Save": "حفظ",
      "Cancel": "إلغاء",
      "Program": "البرنامج",
      "Preferred language": "اللغة المفضلة",
      "Sign-in provider": "مزود تسجيل الدخول",
      "Email verified": "البريد الإلكتروني موثق",
      "Not issued yet": "لم يصدر بعد",
      "Edit user": "تعديل المستخدم",
      "Save changes": "حفظ التغييرات",
      "Delete user": "حذف المستخدم",
      "Edit your profile": "تعديل ملفك الشخصي",
      "Save profile": "حفظ الملف الشخصي",
      "Change password": "تغيير كلمة المرور",
      "Current password": "كلمة المرور الحالية",
      "New password": "كلمة المرور الجديدة",
      "Confirm new password": "تأكيد كلمة المرور الجديدة",
      "Update password": "تحديث كلمة المرور",
      "All roles": "كل الأدوار",
      "All statuses": "كل الحالات"
    }
  };

  let language = readLanguage();

  function readLanguage() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return SUPPORTED.indexOf(stored) !== -1 ? stored : "en";
    } catch (_) {
      return "en";
    }
  }

  function t(key, fallback) {
    if (language === "en") return fallback != null ? fallback : key;
    const table = PHRASES[language] || {};
    if (table[key]) return table[key];
    return fallback != null ? fallback : key;
  }

  function direction(code) {
    return (code || language) === "ar" ? "rtl" : "ltr";
  }

  function applyDocument() {
    document.documentElement.lang = language;
    document.documentElement.dir = direction(language);
    const select = document.getElementById("language-select");
    if (select) select.value = language;
  }

  function setLanguage(code) {
    if (SUPPORTED.indexOf(code) === -1) return;
    language = code;
    try {
      localStorage.setItem(STORAGE_KEY, code);
    } catch (_) {
      /* private mode */
    }
    applyDocument();
    window.dispatchEvent(
      new CustomEvent("deiy:language-changed", { detail: { language: code } })
    );
  }

  function translateTree(root) {
    if (!root || language === "en") return;
    const table = PHRASES[language] || {};
    if (!Object.keys(table).length) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (node) {
      const parent = node.parentNode;
      if (!parent) return;
      const tag = (parent.nodeName || "").toLowerCase();
      if (tag === "script" || tag === "style" || tag === "textarea") return;
      const raw = node.nodeValue || "";
      const key = raw.trim();
      if (!key || !table[key]) return;
      node.nodeValue = raw.replace(key, table[key]);
    });

    ["placeholder", "aria-label", "title", "alt"].forEach(function (attribute) {
      root.querySelectorAll("[" + attribute + "]").forEach(function (element) {
        const value = element.getAttribute(attribute);
        if (value && table[value]) element.setAttribute(attribute, table[value]);
      });
    });
  }

  function bind() {
    const select = document.getElementById("language-select");
    if (select && !select.dataset.bound) {
      select.dataset.bound = "1";
      select.addEventListener("change", function () {
        setLanguage(this.value);
      });
    }
    applyDocument();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }

  DEIY.i18n = {
    t: t,
    setLanguage: setLanguage,
    getLanguage: function () {
      return language;
    },
    languages: SUPPORTED.map(function (code) {
      return { code: code, name: NAMES[code], dir: direction(code) };
    }),
    translateTree: translateTree,
    direction: direction,
    applyDocument: applyDocument
  };
})();
