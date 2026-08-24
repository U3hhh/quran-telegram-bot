# Telegram Quran Bot

هذا المشروع ينشر ثلاث آيات يومياً إلى قناة Telegram. كل تشغيل يرسل آية واحدة قرب الفجر والظهر والمغرب بتوقيت بغداد. يستعمل global ayah IDs من 1 إلى 6236 ولا يكرر ID داخل الدورة.

## الإعداد

1. في Telegram افتح BotFather وأرسل newbot. احتفظ بـ BOT_TOKEN سرياً.
2. أضف bot إلى القناة كـ administrator وفعّل Post Messages.
3. استعمل username عام مثل PublicChannelUsername أو numeric channel ID مثل -1001234567890.
4. ارفع المشروع إلى GitHub مع data/state.json و .github/workflows/quran.yml.
5. أضف Secrets باسم BOT_TOKEN و CHANNEL_ID من Settings ثم Secrets and variables ثم Actions.

## الجدولة

يوجد 3 scheduled executions يومياً فقط، والـ cron يعمل بتوقيت Asia/Baghdad:

- 17 5 يومياً = 05:17 Baghdad = fajr
- 37 12 يومياً = 12:37 Baghdad = dhuhr
- 23 18 يومياً = 18:23 Baghdad = maghrib

TZ مضبوط على Asia/Baghdad. هذه أوقات تقريبية وقد يتأخر GitHub. لتغييرها عدّل cron وشرط github.event.schedule المطابق في quran.yml. للأوقات الموسمية عدّل الثلاثة يدوياً ولا تضف جداول متزامنة حتى يبقى العدد 3 يومياً. لا يوجد push trigger، فلا توجد loop.

## الاختبار

من Actions اختر Run workflow ثم slot manual أو fajr أو dhuhr أو maghrib. محلياً:

    python main.py --dry-run --slot manual
    python main.py --validate

dry-run يجلب ويعرض ولا يرسل ولا يغير state. التشغيل الحقيقي المحلي يحتاج environment variables باسم BOT_TOKEN و CHANNEL_ID فقط.

## state وعدم التكرار

used_ayahs يحوي IDs المنشورة بنجاح، و cycle رقم الدورة، و last_posts آخر 30 slot لمنع duplicate posting. يضاف ID بعد تأكيد Telegram نجاح sendMessage فقط. لا يعاد إرسال طلب Telegram بعد timeout لأن الرسالة قد تكون وصلت.

بعد استعمال كل الآيات يبدأ reset في الذاكرة، ولا يحفظ إلا بعد نجاح أول نشر في الدورة الجديدة. Actions يملك contents: write ويستخدم concurrency group، ثم يعمل commit باسم update Quran bot state ويدفع data/state.json. يمكن إعادة الضبط يدوياً بإيقاف workflow ثم جعل cycle رقماً مناسباً و used_ayahs و last_posts فارغين.

## أخطاء شائعة

missing secrets: تحقق من الاسمين ومن repository الصحيح. Telegram 401 يعني token غير صحيح؛ Telegram 400 يعني channel ID أو administrator permission خطأ. Quran timeout يحتاج إعادة تشغيل لاحقة. عند corrupted state أصلح JSON من آخر commit سليم. إذا لم يتحدث state افحص Workflow permissions و commit step.
