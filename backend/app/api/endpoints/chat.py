"""
Chat endpoints for AI assistant
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select
from pydantic import BaseModel, Field
from typing import Optional

from ...database import get_db
from ...services.ai_service import ai_service
from ...models import Message, MessageStatus, User, StudyGroup, Course, UserRole, QuestionThread, QuestionMessage

logger = logging.getLogger(__name__)

router = APIRouter()

oauth2_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# ════════════════════════════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    course_id: Optional[int] = None

class ChatResponse(BaseModel):
    category: str
    response: str
    escalated: bool = False

# ════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.get("/status")
async def chat_status():
    """Health check for chat endpoint"""
    return {"status": "ok", "message": "Chat service is running"}

@router.post("/test")
async def test_chat_post():
    """Simple POST test - no dependencies"""
    logger.info("Testing POST method on /api/chat/test")
    return {
        "status": "ok",
        "message": "POST method works!",
        "timestamp": "2026-03-27"
    }

@router.post("/ask", response_model=ChatResponse)
async def ask_ai(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_optional)
):
    """
    Ask AI assistant a question.
    
    - Classifies the question (academic, administrative, schedule, general)
    - Responds with helpful information
    - Escalates administrative questions to teacher inbox if needed
    """
    logger.info(f"Received question: {request.message[:50]}...")
    
    escalated = False
    target_teacher_id = None
    sender_id = None
    sender = None
    sender_groups = []
    selected_course_title = None

    # Get user from token if provided
    if token:
        try:
            from jose import jwt
            from ...config import settings
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email = payload.get("sub")
            if email:
                user_result = await db.execute(select(User).where(User.email == email))
                user = user_result.scalars().first()
                if user:
                    sender = user
                    sender_id = user.id
                    logger.info(f"User authenticated: {email}")
        except Exception as e:
            logger.warning(f"Token parsing failed: {e}")
            pass

    # Get user's study groups if authenticated
    if sender_id is not None:
        try:
            groups_result = await db.execute(
                select(StudyGroup)
                .join(StudyGroup.students)
                .where(User.id == sender_id, StudyGroup.is_active == True)
                .options(selectinload(StudyGroup.courses))
            )
            sender_groups = groups_result.scalars().all()
            logger.info(f"Found {len(sender_groups)} study groups for user")
        except Exception as e:
            logger.error(f"Error loading user groups: {e}")

    # Validate course access
    if request.course_id is not None:
        if sender and sender.role == UserRole.student:
            available_course_ids = set()
            for group in sender_groups:
                available_course_ids.update(c.id for c in group.courses)
            if request.course_id not in available_course_ids:
                logger.warning(f"Student tried to access unauthorized course: {request.course_id}")
                raise HTTPException(status_code=403, detail="Selected course is not available for this student")

        try:
            course_result = await db.execute(select(Course).where(Course.id == request.course_id))
            selected_course = course_result.scalars().first()
            if selected_course:
                selected_course_title = selected_course.title
                logger.info(f"Course context: {selected_course_title}")
        except Exception as e:
            logger.error(f"Error loading course: {e}")

    # Get AI response
    logger.debug("Calling AI service...")
    try:
        result = await ai_service.classify_and_respond(
            request.message,
            course_context=selected_course_title,
        )
        logger.info(f"AI classified as: {result.get('category')}")
    except Exception as e:
        logger.error(f"AI service error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Service error: {str(e)}")

    # Store AI questions in the structured questions journal so admins can
    # review real student requests and students have their AI history.
    if sender_id is not None:
        try:
            title = (request.message.strip()[:90] + "...") if len(request.message.strip()) > 90 else request.message.strip()
            ai_thread = QuestionThread(
                student_id=sender_id,
                target_type="ai",
                target_user_id=None,
                course_id=request.course_id,
                title=title or "AI-запит",
                category=result.get("category") or "general",
                status="answered",
                priority="normal",
            )
            db.add(ai_thread)
            await db.flush()
            db.add(QuestionMessage(
                thread_id=ai_thread.id,
                sender_id=sender_id,
                sender_role="student",
                message_text=request.message.strip(),
                is_ai_response=False,
            ))
            db.add(QuestionMessage(
                thread_id=ai_thread.id,
                sender_id=None,
                sender_role="ai",
                message_text=result.get("response", ""),
                is_ai_response=True,
            ))
            await db.flush()
        except Exception as e:
            logger.warning(f"Could not store AI question history: {e}")

    # Escalate administrative questions
    if result.get("category") == "administrative":
        # BLOCK ESCALATIONS FOR GUESTS (unauthenticated users)
        if sender_id is None:
            logger.warning("Guest tried to escalate administrative question - BLOCKING")
            result["response"] = "Для вирішення цього питання необхідна допомога адміністратора. Будь ласка, увійдіть у систему або зареєструйтесь, щоб ми могли зв'язатися з вами."
            escalated = False
        else:
            # ALLOW ESCALATIONS FOR AUTHENTICATED USERS
            try:
                if request.course_id is not None:
                    for group in sender_groups:
                        group_course_ids = [c.id for c in group.courses]
                        if request.course_id in group_course_ids and group.teacher_id is not None:
                            target_teacher_id = group.teacher_id
                            break
                else:
                    teacher_ids = {g.teacher_id for g in sender_groups if g.teacher_id is not None}
                    if len(teacher_ids) == 1:
                        target_teacher_id = next(iter(teacher_ids))

                msg = Message(
                    sender_id=sender_id,
                    receiver_id=target_teacher_id,
                    content=request.message,
                    status=MessageStatus.pending,
                    is_escalated=True
                )
                db.add(msg)
                await db.commit()
                escalated = True
                logger.info(f"Message escalated to teacher (ID: {target_teacher_id})")
            except Exception as e:
                logger.error(f"Escalation error: {e}")

    # Commit AI-history if no escalation commit happened, or finalize pending objects.
    try:
        await db.commit()
    except Exception as e:
        logger.warning(f"Final chat commit skipped/failed: {e}")
        await db.rollback()

    return {
        "category": result["category"],
        "response": result["response"],
        "escalated": escalated,
    }
