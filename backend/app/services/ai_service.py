import google.generativeai as genai
from ..config import settings
from fastapi import HTTPException
import json
import logging

logger = logging.getLogger(__name__)

try:
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini API configured successfully")
    else:
        logger.warning("GEMINI_API_KEY not set in .env")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")

class AIService:
    def __init__(self):
        try:
            # Use gemini-2.5-flash (latest and most capable model)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info("AIService initialized with gemini-2.5-flash")
        except Exception as e:
            logger.error(f"Failed to initialize AIService: {e}", exc_info=True)
            self.model = None

    async def classify_and_respond(self, message_content: str, course_context: str | None = None):
        context_block = ""
        if course_context:
            context_block = f"- **Контекст курсу**: Студент обрав курс \"{course_context}\". Враховуй це як головний предметний контекст для відповіді.\n"

        prompt = f"""
        Ти — офіційний ІІ-асистент навчальної платформи "IT School". 

        Твоя база знань про платформу:
        - **Про платформу**: IT School — це сучасна система для дистанційного навчання.
        - **Сторінки**:
            - `index.html`: Головна сторінка, форма входу та реєстрації.
            - `dashboard.html`: Панель студента з курсами та статистикою.
            - `courses.html`: Каталог усіх доступних курсів та запис на них.
            - `schedule.html`: Тижневий розклад занять та місячний календар.
            - `assignments.html`: Список завдань та їх статус.
            - `grades.html`: Оцінки студента та успішність.
            - `profile.html`: Налаштування профілю та досягнення.
        - **Як зареєструватися**: Нові користувачі реєструються на головній сторінці (`index.html`) через форму входу/реєстрації.
        - **Як записатися на курс**: Перейти на сторінку "Курси" (`courses.html`), обрати цікавий курс та натиснути кнопку запису або звернутися до адміністратора.
        - **Розклад**: Актуальний розклад занять завжди доступний на сторінці `schedule.html`. Студенти можуть переглядати розклад тижнем або місяцем.
        - **Відмітка на парі**: Студенти можуть позначити себе присутнім на парі, натиснувши на заняття в календарі.
        - **Ролі**: В системі є Студенти, Викладачі та Адміністратори.
        {context_block}

        Твоє завдання — класифікувати повідомлення студента та надати відповідь.

        Класифікації:
        1. "academic" - питання щодо навчання, коду, алгоритмів, конкретних предметів.
        2. "administrative" - питання щодо розкладу, оплати, доступу до кабінету, реєстрації, організаційних моментів, відмітки на парах.
        3. "schedule" - прямі запити про розклад занять, коли буде пара, який розклад.
        4. "general" - вітання, загальні фрази, розмови.

        Вимоги до відповіді:
        - Будь привітним та професійним.
        - Якщо "academic": надай корисну відповідь, пояснення або пораду.
        - Якщо "administrative": використовуй свою базу знань, щоб направити користувача на потрібну сторінку. Якщо питання складне, повідом, що запит передано адміністратору.
        - Якщо "schedule": напрями студента на сторінку `schedule.html` для перегляду повного розкладу, поясни як користуватися календарем та відміткою.
        - Якщо "general": відповідай привітно.

        Формат відповіді: СУВОРИЙ JSON
        {{
          "category": "academic" | "administrative" | "schedule" | "general",
          "response": "текст твоєї відповіді"
        }}

        Повідомлення студента: "{message_content}"
        """
        
        try:
            # Check if model is initialized
            if not self.model:
                logger.error("Model not initialized")
                raise Exception("AI Model not initialized")
            
            # Call Gemini API
            logger.debug(f"Sending to Gemini API: {message_content[:50]}...")
            response = self.model.generate_content(prompt)
            
            if not response.parts:
                logger.warning("Empty response from Gemini API")
                return {
                    "category": "general",
                    "response": "На жаль, я не можу відповісти на це питання з міркувань безпеки."
                }
                
            text = response.text
            logger.debug(f"Gemini response: {text[:100]}")
            
            # Clean up potential markdown formatting
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text.strip())
            logger.info(f"AI response classified as: {data.get('category')}")
            return data
        except Exception as e:
            logger.error(f"AI Service Error: {e}", exc_info=True)
            
            # Don't use fallback demo - raise to caller for proper handling
            raise HTTPException(
                status_code=503,
                detail=f"AI Service temporarily unavailable: {str(e)}"
            )

ai_service = AIService()

