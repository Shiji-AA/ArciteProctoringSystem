# models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
import pytz
import time
import io
import wave
import logging
from cloudinary_storage.storage import MediaCloudinaryStorage

logger = logging.getLogger(__name__)

# Timezone helper
INDIA_TZ = pytz.timezone('Asia/Kolkata')

def get_india_time():
    return timezone.now().astimezone(INDIA_TZ)

def get_india_time_str():
    return get_india_time().strftime('%Y-%m-%d %I:%M:%S %p %Z')

# Helper function to convert raw audio bytes to WAV
def create_wav_bytes(raw_audio, channels=1, sampwidth=2, framerate=48000):
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(raw_audio)
    return wav_buffer.getvalue()

# Cloudinary storage for raw files
class RawCloudinaryStorage(MediaCloudinaryStorage):
    """Cloudinary storage for raw files like audio or pdfs"""
    def __init__(self, *args, **kwargs):
        kwargs['resource_type'] = 'raw'
        super().__init__(*args, **kwargs)

# Models
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student', null=True, blank=True)
    name = models.CharField(max_length=255)
    address = models.TextField(null=True, blank=True)
    email = models.EmailField(unique=True)
    department = models.CharField(max_length=50, default="")
    photo = models.ImageField(upload_to='student_photos/', storage=MediaCloudinaryStorage())
    face_encoding = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    feedback = models.TextField(null=True, blank=True, max_length=1000)

    def __str__(self):
        return self.name

class Exam(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exams', null=True, blank=True)
    exam_name = models.CharField(max_length=255, default='Default Exam Name')
    total_questions = models.IntegerField(null=True, blank=True)
    correct_answers = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=50,
        choices=[('ongoing', 'Ongoing'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='ongoing'
    )
    percentage_score = models.FloatField(null=True, blank=True)

    def calculate_percentage(self):
        if self.total_questions and self.total_questions > 0:
            self.percentage_score = round((self.correct_answers / self.total_questions) * 100, 2)
        else:
            self.percentage_score = 0.0
        self.save()

    def __str__(self):
        return f"{self.exam_name} - {self.student.name}"

class CheatingEvent(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='cheating_events',
        blank=True,
        null=True
    )
    cheating_flag = models.BooleanField(default=False)
    event_type = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    detected_objects = models.JSONField(default=list)
    tab_switch_count = models.IntegerField(default=0)

class CheatingImage(models.Model):
    event = models.ForeignKey(CheatingEvent, on_delete=models.CASCADE, related_name='cheating_images')
    image = models.ImageField(upload_to='cheating_images/', storage=MediaCloudinaryStorage())
    timestamp = models.DateTimeField(default=timezone.now)

class CheatingAudio(models.Model):
    event = models.ForeignKey(CheatingEvent, on_delete=models.CASCADE, related_name='cheating_audios')
    audio = models.FileField(upload_to='cheating_audios/', blank=True, null=True, storage=RawCloudinaryStorage())
    timestamp = models.DateTimeField(default=timezone.now)

# Utility function to save audio
def save_cheating_audio(audio_data, cheating_event):
    """
    Converts raw audio bytes to WAV and saves to Cloudinary under CheatingAudio
    """
    if not audio_data or not cheating_event:
        logger.warning("Audio data or CheatingEvent is missing")
        return None

    try:
        wav_data = create_wav_bytes(audio_data, channels=1, sampwidth=2, framerate=48000)
        cheating_audio = CheatingAudio(event=cheating_event)
        cheating_audio.audio.save(
            f"cheating_audio_{int(time.time())}.wav",
            ContentFile(wav_data),
            save=True
        )
        return cheating_audio
    except Exception as e:
        logger.error(f"Error saving cheating audio: {e}")
        return None
