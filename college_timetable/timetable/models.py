
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q
# ==================================================
# 1. THỜI GIAN & CẤU HÌNH
# ==================================================

class AcademicYear(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Năm học")
    note = models.TextField(blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "1. Quản lý Năm học"

    def __str__(self):
        return self.code

class Semester(models.Model):
    """
    Quản lý Học kỳ riêng biệt (Để HK2 bắt đầu lại từ Tuần 1)
    Ví dụ: Năm học 2025-2026 có HK1, HK2
    """
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, verbose_name="Thuộc Năm học"
    )
    code = models.CharField(max_length=20, verbose_name="Mã Học kỳ")  # VD: HK1, HK2
    name = models.CharField(max_length=100, verbose_name="Tên hiển thị")
    start_date = models.DateField(verbose_name="Ngày bắt đầu (Tuần 1)",null=True, blank=True) #mới thêm blank với null
    weeks = models.IntegerField(default=15, verbose_name="Tổng số tuần (không tính tuần nghỉ)",null=True, blank=True) #mới thêm blank với null

    class Meta:
        unique_together = ("academic_year", "code")
        verbose_name_plural = "1.1 Cấu hình Học kỳ"
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.code} ({self.academic_year.code})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Sau khi lưu Semester, nếu có start_date và weeks thì tự sinh tuần
        try:
            from .services import generate_semester_weeks
            if self.start_date and self.weeks:
                generate_semester_weeks(self, delete_old=True)
        except Exception as e:
            # Không nên raise để tránh lỗi khi lưu Admin, chỉ log nếu cần
            print(f"[Semester.save] Lỗi generate_semester_weeks: {e}")    

class SemesterBreak(models.Model):
    """
    Khoảng thời gian nghỉ (Tết, Lễ...) gắn với Học kỳ.
    Dùng để đánh dấu những ngày/tuần không dạy.
    """
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, verbose_name="Thuộc Học kỳ")
    name = models.CharField(max_length=100, verbose_name="Tên kỳ nghỉ")
    start_date = models.DateField(verbose_name="Từ ngày",null=True, blank=True) #mới thêm blank với null
    end_date = models.DateField(verbose_name="Đến ngày",null=True, blank=True) #mới thêm blank với null

    class Meta:
        verbose_name_plural = "1.2 Cấu hình Thời gian nghỉ"

    def __str__(self):
        return self.name

class PublicHoliday(models.Model):
    date = models.DateField(unique=True, verbose_name="Ngày nghỉ")
    name = models.CharField(max_length=100, verbose_name="Tên ngày lễ")
    is_recurring = models.BooleanField(default=False, verbose_name="Lặp lại hàng năm")

    class Meta:
        verbose_name_plural = "1.3 Danh sách Ngày Lễ"

    def __str__(self):
        return f"{self.date.strftime('%d/%m')} - {self.name}"

class SemesterWeek(models.Model):
    """
    Tuần trong Học kỳ. Có thể generate tự động từ start_date + số tuần,
    và đánh dấu tuần nghỉ (Tết) bằng is_break=True.
    """
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="semester_weeks", verbose_name="Học kỳ")
    index = models.IntegerField(verbose_name="Tuần thứ")  # 1..N (không tính tuần nghỉ)
    start_date = models.DateField(verbose_name="Ngày bắt đầu tuần",null=True, blank=True) #mới thêm blank với null
    end_date = models.DateField(verbose_name="Ngày kết thúc tuần",null=True, blank=True) #mới thêm blank với null
    is_break = models.BooleanField(default=False, verbose_name="Tuần nghỉ")

    class Meta:
        verbose_name_plural = "1.4 Cấu hình Tuần trong Học kỳ"
        unique_together = ("semester", "index")
        ordering = ["semester", "index"]

    def __str__(self):
        return f"{self.semester} - Tuần {self.index}"

class PeriodSlot(models.Model):
    """
    Khung tiết trong ngày. Ví dụ:
    - Tiết 1: 07:30–08:15
    - ...
    Dùng để map sang buổi sáng/chiều, LT/TH, nếu cần chi tiết theo giờ.
    """
    index = models.IntegerField(verbose_name="Tiết thứ")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu",null=True, blank=True) #mới thêm blank với null
    end_time = models.TimeField(verbose_name="Giờ kết thúc",null=True, blank=True) #mới thêm blank với null

    class Meta:
        verbose_name_plural = "1.5 Cấu hình Tiết học"
        ordering = ["index"]

    def __str__(self):
        return f"Tiết {self.index} ({self.start_time}-{self.end_time})"

# ==================================================
# 2. DANH MỤC CHUNG
# ==================================================

class TrainingLevel(models.Model):
    """
    Bậc đào tạo: Cao đẳng, Trung cấp...
    """
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Bậc")  # VD: CD, TC
    name = models.CharField(max_length=100, verbose_name="Tên Bậc")
    form = models.CharField(max_length=50, default="Tập trung", verbose_name="Hình thức")
    duration_semesters = models.IntegerField(default=5, verbose_name="Số Học kỳ toàn khoá")

    class Meta:
        verbose_name_plural = "2. Quản lý Bậc Đào tạo"

    def __str__(self):
        return f"{self.name} ({self.code})"

class Department(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Khoa")
    name = models.CharField(max_length=100, verbose_name="Tên Khoa")

    class Meta:
        verbose_name_plural = "3. Quản lý Khoa"

    def __str__(self):
        return self.name

class SpecializationGroup(models.Model):
    """
    Nhóm chuyên môn (VD: Lập trình, Mạng, Thiết kế...).
    Dùng cho:
    - Môn học yêu cầu nhóm chuyên môn
    - Phòng học có khả năng cho nhóm chuyên môn
    """
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Nhóm")
    name = models.CharField(max_length=100, verbose_name="Tên Nhóm chuyên môn")

    class Meta:
        verbose_name_plural = "4. Cấu hình Nhóm Chuyên môn"

    def __str__(self):
        return self.name

# ==================================================
# 3. NGÀNH, CHƯƠNG TRÌNH ĐÀO TẠO
# ==================================================

class Major(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Ngành")
    name = models.CharField(max_length=100, verbose_name="Tên Ngành")
    level = models.ForeignKey(TrainingLevel, on_delete=models.CASCADE, verbose_name="Thuộc Bậc")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Khoa quản lý")
    is_general = models.BooleanField(
        default=False, verbose_name="Là Nhóm Môn chung (nếu dùng như một 'ngành' môn chung)"
    )
    total_credits = models.FloatField(
        default=0, null=True, blank=True, verbose_name="Tổng Tín chỉ"
    )
    total_semesters = models.IntegerField(
        default=0, null=True, blank=True, verbose_name="Số Học kỳ"
    )

    class Meta:
        verbose_name_plural = "5. Quản lý Ngành"

    def __str__(self):
        return f"{self.name} - {self.level.code}"

# class Curriculum(models.Model):
#     """
#     Chương trình đào tạo theo Khoá.
#     Mỗi Ngành + Khoá tuyển (Năm học) có 1 Curriculum riêng.
#     """
#     major = models.ForeignKey(Major, on_delete=models.CASCADE, verbose_name="Ngành")
#     intake_year = models.ForeignKey(
#         AcademicYear, on_delete=models.CASCADE, verbose_name="Khoá tuyển/Năm nhập học"
#     )
#     name = models.CharField(
#         max_length=100, blank=True, verbose_name="Tên CTĐT (tuỳ chọn, để phân biệt)"
#     )

#     class Meta:
#         verbose_name_plural = "5.1 Chương trình đào tạo theo Khoá"
#         unique_together = ("major", "intake_year")

#     def __str__(self):
#         return f"{self.major.name} - Khoá {self.intake_year.code}"


# class Curriculum(models.Model):
#     major = models.ForeignKey(Major, on_delete=models.CASCADE, verbose_name="Ngành")
#     intake_year = models.ForeignKey(
#         AcademicYear, on_delete=models.CASCADE, verbose_name="Khoá tuyển/Năm nhập học"
#     )
#     name = models.CharField(
#         max_length=100, blank=True, verbose_name="Tên CTĐT (tuỳ chọn, để phân biệt)"
#     )

#     class Meta:
#         verbose_name_plural = "5.1 Chương trình đào tạo theo Khoá"
#         unique_together = ("major", "intake_year")

#     def __str__(self):
#         return f"{self.major.name} - Khoá {self.intake_year.code}"

#     # 👇 Thêm hàm này
#     @transaction.atomic
#     def generate_curriculum_subjects(self, overwrite=False):
#         """
#         Tự động sinh CurriculumSubject cho CTĐT này.

#         Quy tắc:
#         - Lấy tất cả Subject:
#             + môn chuyên ngành: subject.major == self.major
#             + môn chung: subject.major is null
#         - Học kỳ:
#             + ưu tiên subject.semester_number
#             + giới hạn trong [1 .. duration_semesters] theo bậc đào tạo
#         - Môn tự chọn: hiện tại xử lý như môn thường (is_optional=False)

#         Tham số:
#         - overwrite=False: nếu True thì update lại semester_index, total_periods,
#           is_optional cho những CurriculumSubject đã tồn tại.
#         """
#         from .models import Subject, CurriculumSubject  # tránh import vòng

#         # Số học kỳ tối đa của CTĐT (TC: 4, CD: 5...)
#         duration = self.major.level.duration_semesters or 5

#         # Lấy môn chuyên ngành + môn chung
#         subjects = Subject.objects.filter(
#             Q(major=self.major) | Q(major__isnull=True)
#         ).distinct()

#         created_count = 0
#         updated_count = 0
#         skipped_count = 0

#         for subj in subjects:
#             # Học kỳ gốc từ môn
#             sem = subj.semester_number or 1

#             # Nếu vượt quá số học kỳ CTĐT thì ép về học kỳ cuối
#             if sem > duration:
#                 sem = duration

#             defaults = {
#                 "semester_index": sem,
#                 "total_periods": subj.total_periods,
#                 "is_optional": False,  # hiện tại treat như môn thường
#             }

#             cs, created = CurriculumSubject.objects.get_or_create(
#                 curriculum=self,
#                 subject=subj,
#                 defaults=defaults,
#             )

#             if created:
#                 created_count += 1
#             else:
#                 if overwrite:
#                     # cập nhật lại thông tin nếu muốn
#                     for field, value in defaults.items():
#                         setattr(cs, field, value)
#                     cs.save(update_fields=list(defaults.keys()))
#                     updated_count += 1
#                 else:
#                     skipped_count += 1

#         return {
#             "created": created_count,
#             "updated": updated_count,
#             "skipped": skipped_count,
#         }

# models.py
from django.db import models, transaction
from django.db.models import Q

class Curriculum(models.Model):
    major = models.ForeignKey(Major, on_delete=models.CASCADE, verbose_name="Ngành")
    intake_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, verbose_name="Khoá tuyển/Năm nhập học"
    )
    name = models.CharField(
        max_length=100, blank=True, verbose_name="Tên CTĐT (tuỳ chọn, để phân biệt)"
    )

    class Meta:
        verbose_name_plural = "5.1 Chương trình đào tạo theo Khoá"
        unique_together = ("major", "intake_year")

    def __str__(self):
        return f"{self.major.name} - Khoá {self.intake_year.code}"

    @transaction.atomic
    def generate_curriculum_subjects(self, overwrite=False):
        """
        Sinh CurriculumSubject cho CTĐT này.

        Quy tắc:
        - Lấy Subject:
            + Môn chuyên ngành: subject.major == self.major
            + Môn chung: subject.major is null
        - Học kỳ:
            + ưu tiên subject.semester_number
            + ép vào [1 .. duration_semesters] (theo bậc đào tạo: TC thường 4, CD thường 5)
        - Môn tự chọn hiện tại = môn thường (is_optional=False)

        overwrite=False:
            - False: nếu đã có CurriculumSubject thì bỏ qua
            - True: update lại semester_index, total_periods, is_optional
        """
        from .models import Subject, CurriculumSubject  # tránh import vòng

        duration = self.major.level.duration_semesters or 5  # 4 hoặc 5 tuỳ bậc

        subjects = Subject.objects.filter(
            Q(major=self.major) | Q(major__isnull=True)
        ).distinct()

        created = updated = skipped = 0

        for subj in subjects:
            sem = subj.semester_number or 1
            if sem > duration:
                sem = duration
            if sem < 1:
                sem = 1

            defaults = {
                "semester_index": sem,
                "total_periods": subj.total_periods,
                "is_optional": False,
            }

            cs, is_created = CurriculumSubject.objects.get_or_create(
                curriculum=self,
                subject=subj,
                defaults=defaults,
            )

            if is_created:
                created += 1
            else:
                if overwrite:
                    for field, value in defaults.items():
                        setattr(cs, field, value)
                    cs.save(update_fields=list(defaults.keys()))
                    updated += 1
                else:
                    skipped += 1

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
        }

# ==================================================
# 4. MÔN HỌC, CẤU TRÚC MÔN
# ==================================================

class RoomType(models.Model):
    """
    Loại phòng: LT, TH_MMT, TH_MANG, ONLINE, PE (Sân TD)...
    """
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Loại")
    name = models.CharField(max_length=100, verbose_name="Tên Loại phòng")

    class Meta:
        verbose_name_plural = "9. Cấu hình Loại phòng"

    def __str__(self):
        return self.name

class Subject(models.Model):
    """
    Môn học/Mô-đun.
    - subject_type: phân biệt Lý thuyết, Thực hành, Tích hợp, Thực tập
    - major: ngành chính (có thể null nếu là môn đại cương cho nhiều ngành)
    """
    SUBJECT_TYPE_CHOICES = [
        ("TN", "Trắc nghiệm"),
        ("TL", "Tự luận"),
        ("TH", "Thực hành trên máy"),
        ("BC", "Báo cáo / Tiểu luận"),
        ("KHAC", "Khác"),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Môn/Mô-đun")
    name = models.CharField(max_length=200, verbose_name="Tên Môn học/Mô-đun")

    major = models.ForeignKey(
        Major,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ngành (nếu là môn chuyên ngành)"
    )
    managing_department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Khoa phụ trách"
    )

    subject_type = models.CharField(
        max_length=20, choices=SUBJECT_TYPE_CHOICES, verbose_name="Loại môn"
    )

    # Tổng số tiết/giờ cho cả môn (có thể override theo CurriculumSubject)
    total_periods = models.FloatField(verbose_name="Tổng số Tiết/Giờ")

    # Sĩ số tối đa cho 1 lớp học phần
    max_class_size = models.IntegerField(default=35, verbose_name="Sĩ số tối đa/lớp HP")

    # Yêu cầu về phòng và nhóm chuyên môn
    required_room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Yêu cầu Loại phòng"
    )
    specialization_group = models.ForeignKey(
        SpecializationGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Yêu cầu Nhóm chuyên môn"
    )

    # Môn đại cương do khoa khác quản lý, khoa CNTT chỉ nhận TKB phần của mình
    is_external_managed = models.BooleanField(
        default=False,
        verbose_name="Môn do đơn vị khác xếp TKB (không xếp trong hệ thống này)"
    )
    exam_form = models.CharField(
        max_length=10,
        choices=SUBJECT_TYPE_CHOICES,
        default="TN",
        verbose_name="Hình thức thi chính",
    )
    # true nếu có tổ chức buổi chấm riêng (thực hành trên máy…)
    has_separate_marking = models.BooleanField(
        default=False,
        verbose_name="Có chấm thi riêng (sau đợt thi)",
        help_text="Mặc định chỉ bật đối với các môn thực hành trên máy.",
    )
    semester_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Học kỳ (số)",
        help_text="Nhập số học kỳ: 1, 2, 3, 4, 5"
    )
    class Meta:
        verbose_name_plural = "7. Quản lý Môn học"

    def __str__(self):
        return f"{self.name} ({self.code})"

class CurriculumSubject(models.Model):
    """
    Môn trong CTĐT cụ thể (Khoá + Ngành).
    Mỗi khoá có danh mục môn riêng, thứ tự học kỳ riêng.
    """
    curriculum = models.ForeignKey(
        Curriculum, on_delete=models.CASCADE, related_name="subjects", verbose_name="Chương trình"
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Môn học")
    semester_index = models.IntegerField(verbose_name="Học kỳ (trong CTĐT)")
    is_optional = models.BooleanField(default=False, verbose_name="Môn tự chọn")

    # Cho phép override số tiết nếu môn này ở khoá này khác chuẩn
    total_periods = models.FloatField(
        null=True, blank=True, verbose_name="Tổng tiết (nếu khác Subject)"
    )

    class Meta:
        verbose_name_plural = "5.2 Cấu hình Môn trong CTĐT"
        unique_together = ("curriculum", "subject")

    def __str__(self):
        return f"{self.subject.name} - HK {self.semester_index} ({self.curriculum})"

class SubjectChapter(models.Model):
    """
    Cấu trúc môn: các chương/bài và số tiết tương ứng.
    """
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="chapters", verbose_name="Môn học"
    )
    index = models.IntegerField(verbose_name="Thứ tự Chương/Bài")
    name = models.CharField(max_length=255, verbose_name="Tên Chương/Bài")
    periods = models.FloatField(verbose_name="Số tiết của Chương/Bài")

    class Meta:
        verbose_name_plural = "7.1 Cấu trúc Chương/Bài Môn học"
        ordering = ["subject", "index"]

    def __str__(self):
        return f"{self.subject.code} - Chương {self.index}: {self.name}"

class AssessmentComponent(models.Model):
    """
    Cấu trúc đánh giá của môn: KT thường xuyên, định kỳ, GK, CK...
    """
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="assessments", verbose_name="Môn học"
    )
    name = models.CharField(max_length=100, verbose_name="Tên thành phần")
    weight = models.FloatField(verbose_name="Trọng số (%)")

    ASSESS_FORM_CHOICES = [
        ("MCQ", "Trắc nghiệm"),
        ("WRITTEN", "Tự luận"),
        ("PRACTICE_PC", "Thực hành trên máy"),
        ("REPORT", "Báo cáo tiểu luận"),
        ("OTHER", "Khác"),
    ]

    form = models.CharField(
        max_length=50,
        choices=ASSESS_FORM_CHOICES,
        verbose_name="Hình thức đánh giá/thi"
    )

    is_final_exam = models.BooleanField(default=False, verbose_name="Là thi kết thúc học phần?")
    duration_minutes = models.IntegerField(
        null=True, blank=True, verbose_name="Thời lượng (phút, nếu là bài thi)"
    )

    class Meta:
        verbose_name_plural = "7.2 Cấu trúc Đánh giá Môn học"

    def __str__(self):
        return f"{self.subject.code} - {self.name} ({self.weight}%)"

# ==================================================
# 5. PHÒNG HỌC
# ==================================================

class Room(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Phòng")
    name = models.CharField(max_length=100, verbose_name="Tên Phòng")
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, verbose_name="Loại phòng")
    capacity = models.IntegerField(default=0, verbose_name="Sức chứa tối đa")

    # phòng dạy được nhóm chuyên môn nào
    capabilities = models.ManyToManyField(
        SpecializationGroup, through="RoomCapability", blank=True, verbose_name="Nhóm chuyên môn"
    )

    # nếu để trống -> dùng cho mọi ngành; nếu có -> ưu tiên/giới hạn cho một số ngành
    allowed_majors = models.ManyToManyField(
        Major, blank=True, verbose_name="Ưu tiên/cho phép cho các Ngành"
    )

    class Meta:
        verbose_name_plural = "10. Quản lý Phòng học"

    def __str__(self):
        return self.code


class RoomCapability(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    group = models.ForeignKey(SpecializationGroup, on_delete=models.CASCADE)
    priority = models.IntegerField(
        default=1, choices=((1, "Ưu tiên 1"), (2, "Ưu tiên 2"), (3, "Ưu tiên 3"))
    )

    class Meta:
        unique_together = ("room", "group")
        verbose_name_plural = "10.1 Khả năng chuyên môn của Phòng"

# ==================================================
# 6. LỚP SINH VIÊN
# ==================================================

class StudentClass(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã Lớp")
    name = models.CharField(max_length=100, verbose_name="Tên Lớp")
    size = models.IntegerField(default=0, verbose_name="Sĩ số")

    major = models.ForeignKey(Major, on_delete=models.CASCADE, verbose_name="Ngành")
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, verbose_name="Khoá/Năm nhập học"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, verbose_name="Khoa quản lý"
    )

    homeroom_teacher = models.ForeignKey(
        "Instructor", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="GVCN"
    )

    class Meta:
        verbose_name_plural = "8. Quản lý Lớp Sinh viên"

    def __str__(self):
        return self.code

# ==================================================
# 7. GIẢNG VIÊN & NĂNG LỰC
# ==================================================

class InstructorRole(models.Model):
    """
    Vai trò ảnh hưởng đến giảm giờ chuẩn: Trưởng khoa, Phó khoa, GVCN, Bí thư đoàn...
    workload_reduction: 0.3 = giảm 30% giờ chuẩn.
    """
    name = models.CharField(max_length=100, verbose_name="Tên vai trò")
    workload_reduction = models.FloatField(
        default=0.0, verbose_name="Tỉ lệ giảm giờ chuẩn (0.3 = giảm 30%)"
    )

    class Meta:
        verbose_name_plural = "6.1 Cấu hình Vai trò Giảng viên"

    def __str__(self):
        return self.name

class Instructor(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã GV")
    name = models.CharField(max_length=100, verbose_name="Họ tên")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="Thuộc Khoa")
    is_leader = models.BooleanField(default=False, verbose_name="Là Lãnh đạo (cờ tổng quát)")

    teaching_quota = models.FloatField(default=415, verbose_name="Định mức GIẢNG DẠY (Tiết)")
    admin_quota = models.FloatField(default=480, verbose_name="Định mức HÀNH CHÍNH (Giờ)")
    conversion_ratio = models.FloatField(default=3.2, verbose_name="Hệ số quy đổi giờ chuẩn → giờ HC")

    max_subjects_per_semester = models.IntegerField(
        default=3, verbose_name="Tối đa môn được phân dạy mỗi Học kỳ"
    )

    # vai trò: Trưởng khoa, Phó khoa, GVCN, Bí thư đoàn...
    roles = models.ManyToManyField(
        InstructorRole, blank=True, verbose_name="Vai trò (ảnh hưởng giảm giờ chuẩn)"
    )

    # GV có thể dạy cho những Ngành nào, và có dạy được môn chung không
    allowed_majors = models.ManyToManyField(
        Major, blank=True, verbose_name="Được phân dạy cho các Ngành"
    )
    can_teach_general = models.BooleanField(
        default=False, verbose_name="Có dạy được các môn chung (đại cương)?"
    )

    # Khả năng giảng dạy theo Môn (Mức ưu tiên)
    competencies = models.ManyToManyField(
        Subject,
        through="InstructorCompetency",
        verbose_name="Khả năng giảng dạy (theo Môn)",
        blank=True,
    )

    class Meta:
        verbose_name_plural = "6. Quản lý Giảng viên"

    def __str__(self):
        return self.name

class InstructorCompetency(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    priority = models.IntegerField(
        default=1, choices=((1, "Ưu tiên 1"), (2, "Ưu tiên 2"), (3, "Ưu tiên 3"))
    )

    class Meta:
        unique_together = ("instructor", "subject")
        verbose_name_plural = "6.2 Khả năng giảng dạy của GV"

class InstructorAvailability(models.Model):
    """
    Khả dụng thời gian của GV:
    - is_available = False => không xếp dạy (VD sáng thứ 2 lãnh đạo họp, các slot bận khác).
    """
    instructor = models.ForeignKey(
        Instructor, on_delete=models.CASCADE, related_name="availabilities"
    )
    day_of_week = models.IntegerField(verbose_name="Thứ (2=1 ... CN=7)")
    start_period = models.IntegerField(verbose_name="Tiết bắt đầu")
    end_period = models.IntegerField(verbose_name="Tiết kết thúc")
    is_available = models.BooleanField(default=True, verbose_name="Có thể dạy?")

    class Meta:
        verbose_name_plural = "6.3 Khung thời gian rảnh/bận của GV"

class WorkloadReductionType(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Mã loại giảm")
    name = models.CharField(max_length=100, verbose_name="Tên loại giảm")
    teaching_reduction_percent = models.FloatField(
        default=0,
        verbose_name="Giảm ĐM GIẢNG DẠY (%)",
    )
    admin_reduction_percent = models.FloatField(
        default=0,
        verbose_name="Giảm ĐM HÀNH CHÍNH (%)",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "15.1 Danh mục Loại giảm định mức"

    def __str__(self):
        return f"{self.name} ({self.code})"

class InstructorDuty(models.Model):
    instructor = models.ForeignKey(
        Instructor,
        on_delete=models.CASCADE,
        related_name="duties",
        verbose_name="Giảng viên",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        verbose_name="Năm học",
    )
    reduction_type = models.ForeignKey(
        WorkloadReductionType,
        on_delete=models.CASCADE,
        verbose_name="Loại giảm",
    )
    months = models.PositiveSmallIntegerField(
        default=10,
        verbose_name="Số tháng được giảm",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "15.2 Phân công Giảm định mức GV"
        # unique_together = ("instructor", "academic_year", "reduction_type")

    def __str__(self):
        return f"{self.reduction_type.name} - {self.instructor.name} ({self.academic_year.code})"

# ==================================================
# 8. LỚP HỌC PHẦN & THỜI KHOÁ BIỂU
# ==================================================

class CourseSection(models.Model):
    """
    Lớp học phần: đơn vị để phân công GV, xếp TKB, lên lịch thi.
    Ví dụ: CĐCNTT_K25_MH01_01
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Môn học")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, verbose_name="Học kỳ")
    code = models.CharField(max_length=50, verbose_name="Mã Lớp HP")

    # Có thể gộp nhiều lớp sinh viên cùng học
    classes = models.ManyToManyField(
        StudentClass, related_name="course_sections", verbose_name="Các Lớp sinh viên"
    )

    instructor = models.ForeignKey(
        Instructor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Giảng viên chính"
    )

    # Tổng số tiết phải dạy cho lớp học phần này
    planned_periods = models.FloatField(
        null=True, blank=True, verbose_name="Tổng số tiết của Lớp HP"
    )

    # Nếu môn chỉ dạy trong một khoảng tuần (vd: từ tuần 10, hoặc rút gọn 10 tuần)
    start_week = models.IntegerField(
        null=True, blank=True, verbose_name="Bắt đầu từ Tuần (nếu khác Tuần 1)"
    )
    week_count = models.IntegerField(
        null=True, blank=True, verbose_name="Số tuần dạy (nếu rút gọn)"
    )
    sessions_per_week = models.IntegerField(
        default=1, verbose_name="Số buổi/tuần dự kiến (để engine auto xếp)"
    )

    is_locked = models.BooleanField(
        default=False,
        verbose_name="Khoá Lớp HP (không tự động thay đổi khi chạy auto xếp TKB)",
    )

    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "16. Lớp học phần"
        unique_together = ("semester", "code")

    def __str__(self):
        return f"{self.code} - {self.subject.name}"


class TeachingSlot(models.Model):
    """
    Một "buổi học" cụ thể trong TKB:
    - Thuộc Lớp HP
    - Thứ, Tiết bắt đầu/kết thúc
    - Phòng
    - Học ở những Tuần nào
    """
    course_section = models.ForeignKey(
        CourseSection, on_delete=models.CASCADE, related_name="slots", verbose_name="Lớp học phần"
    )
    room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Phòng"
    )

    day_of_week = models.IntegerField(verbose_name="Thứ (2=1 ... CN=7)")
    start_period = models.IntegerField(verbose_name="Tiết bắt đầu")
    end_period = models.IntegerField(verbose_name="Tiết kết thúc")

    weeks = models.ManyToManyField(
        SemesterWeek, related_name="teaching_slots", verbose_name="Các tuần học"
    )

    method = models.CharField(max_length=50, blank=True, verbose_name="Phương thức dạy")
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Khoá Slot (không chỉnh sửa khi auto xếp lại)",
    )

    class Meta:
        verbose_name_plural = "19. Chi tiết Thời khoá biểu"
        ordering = ["day_of_week", "start_period"]

    def __str__(self):
        return f"{self.course_section.code} - Thứ {self.day_of_week}, Tiết {self.start_period}-{self.end_period}"

# ==================================================
# 9. THI, COI THI, CHẤM THI
# ==================================================

# class ExamSession(models.Model):
#     """
#     Lịch thi cho Lớp học phần (thi kết thúc học phần hoặc thành phần đánh giá).
#     """
#     course_section = models.ForeignKey(
#         CourseSection, on_delete=models.CASCADE, related_name="exams", verbose_name="Lớp học phần"
#     )
#     component = models.ForeignKey(
#         AssessmentComponent,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         verbose_name="Thuộc thành phần đánh giá",
#     )

#     date = models.DateField(verbose_name="Ngày thi")
#     start_time = models.TimeField(verbose_name="Giờ bắt đầu")
#     duration_minutes = models.IntegerField(verbose_name="Thời lượng (phút)")
#     room = models.ForeignKey(
#         Room, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Phòng thi"
#     )

#     # Giám thị (coi thi) - phân vai qua bảng trung gian
#     invigilators = models.ManyToManyField(
#         Instructor,
#         through="ExamInvigilationAssignment",
#         related_name="invigilated_exams",
#         blank=True,
#         verbose_name="Giám thị",
#     )

#     class Meta:
#         verbose_name_plural = "21. Lịch thi"

#     def __str__(self):
#         return f"Thi {self.course_section.code} - {self.date} {self.start_time}"

# class ExamInvigilationAssignment(models.Model):
#     """
#     Phân công coi thi: Giám thị 1, Giám thị 2, Dự phòng...
#     """
#     ROLE_CHOICES = [
#         ("GT1", "Giám thị 1"),
#         ("GT2", "Giám thị 2"),
#         ("RESERVE", "Giám thị dự phòng"),
#     ]

#     exam_session = models.ForeignKey(
#         ExamSession,
#         on_delete=models.CASCADE,
#         related_name="invigilation_assignments",
#         verbose_name="Ca thi"
#     )
#     instructor = models.ForeignKey(
#         Instructor,
#         on_delete=models.CASCADE,
#         related_name="exam_invigilation_assignments",
#         verbose_name="Giảng viên"
#     )
#     role = models.CharField(
#         max_length=20,
#         choices=ROLE_CHOICES,
#         verbose_name="Vai trò trong ca thi"
#     )

#     class Meta:
#         verbose_name_plural = "21.1 Phân công Coi thi"
#         unique_together = ("exam_session", "instructor", "role")

#     def __str__(self):
#         return f"{self.exam_session} - {self.instructor.name} ({self.get_role_display()})"

# class ExamGradingAssignment(models.Model):
#     """
#     Phân công chấm thi: Giám khảo 1, Giám khảo 2, Phúc khảo...
#     """
#     ROLE_CHOICES = [
#         ("GK1", "Giám khảo 1"),
#         ("GK2", "Giám khảo 2"),
#         ("REVIEW", "Phúc khảo/Chấm lại"),
#     ]

#     exam_session = models.ForeignKey(
#         ExamSession,
#         on_delete=models.CASCADE,
#         related_name="grading_assignments",
#         verbose_name="Ca thi"
#     )
#     instructor = models.ForeignKey(
#         Instructor,
#         on_delete=models.CASCADE,
#         related_name="exam_grading_assignments",
#         verbose_name="Giảng viên chấm thi"
#     )
#     role = models.CharField(
#         max_length=20,
#         choices=ROLE_CHOICES,
#         verbose_name="Vai trò chấm thi"
#     )

#     # Thời gian chấm (thường 1–2 tuần sau ngày thi)
#     start_date = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu chấm")
#     end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc chấm")

#     class Meta:
#         verbose_name_plural = "21.2 Phân công Chấm thi"

#     def __str__(self):
#         return f"{self.exam_session} - {self.instructor.name} ({self.get_role_display()})"

# ==================================================
# 10. HOẠT ĐỘNG KHÁC (TÍNH TẢI GIẢNG VIÊN)
# ==================================================

# class ResearchCategory(models.Model):
#     """
#     Danh mục các loại NCKH và quy đổi giờ/đơn vị.
#     Ví dụ:
#       - BSGT_TINCHI: Biên soạn giáo trình (tín chỉ), 60 giờ/tín chỉ
#       - BAO_KHOA_HOC: Viết bài báo, 10 giờ/bài
#       - NHCH_TL: Ngân hàng câu hỏi tự luận, X giờ/đề
#       - NHCH_TN: Ngân hàng câu hỏi trắc nghiệm, Y giờ/câu
#     """
#     code = models.CharField(max_length=30, unique=True, verbose_name="Mã loại NCKH")
#     name = models.CharField(max_length=255, verbose_name="Tên nội dung NCKH")
#     unit_label = models.CharField(
#         max_length=50,
#         verbose_name="Đơn vị tính",
#         help_text="VD: tín chỉ, bài, đề, câu hỏi...",
#     )
#     default_hours_per_unit = models.FloatField(
#         default=0,
#         verbose_name="Giờ chuẩn / 1 đơn vị",
#         help_text="VD: 60 giờ/tín chỉ; 10 giờ/bài; 0.5 giờ/câu TN...",
#     )
#     note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

#     class Meta:
#         verbose_name_plural = "16. Danh mục NCKH (quy đổi)"

#     def __str__(self):
#         return f"{self.name} ({self.code})"

class ResearchCategory(models.Model):
    code = models.CharField(max_length=30, unique=True, verbose_name="Mã loại NCKH")
    name = models.CharField(max_length=255, verbose_name="Tên nội dung NCKH")
    unit_label = models.CharField(
        max_length=50,
        verbose_name="Đơn vị tính",
        help_text="VD: tín chỉ, bài, đề, câu hỏi...",
    )
    default_hours_per_unit = models.FloatField(
        default=0,
        verbose_name="Giờ chuẩn / 1 đơn vị",
        help_text="VD: 60 giờ/tín chỉ; 10 giờ/bài; 0.5 giờ/câu TN...",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "16. Danh mục NCKH (quy đổi)"

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        """
        Mỗi lần thay đổi giờ quy đổi (default_hours_per_unit),
        tự động cập nhật lại 'hours' cho tất cả đề tài thuộc loại này.
        """
        super().save(*args, **kwargs)

        # Import ở đây (hoặc dùng trực tiếp ResearchProject nếu cùng file)
        from .models import ResearchProject

        projects = ResearchProject.objects.filter(category=self)
        for p in projects:
            # dùng lại hàm tính giờ trong ResearchProject
            try:
                new_hours = p.calc_hours()
            except AttributeError:
                # nếu bạn chưa có calc_hours thì dùng công thức trực tiếp:
                # new_hours = (p.quantity or 0) * (self.default_hours_per_unit or 0)
                new_hours = (p.quantity or 0) * (self.default_hours_per_unit or 0)

            if p.hours != new_hours:
                p.hours = new_hours
                p.save(update_fields=["hours"])

class ResearchProject(models.Model):
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    category = models.ForeignKey(
        ResearchCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Loại NCKH",
    )
    topic_name = models.CharField(max_length=255, verbose_name="Tên đề tài / nội dung")
    quantity = models.FloatField(
        default=1,
        verbose_name="Số lượng đơn vị",
        help_text="VD: số tín chỉ, số bài báo, số câu hỏi...",
    )
    hours = models.FloatField(
        default=0,
        editable=False,   # ⬅ KHÔNG cho sửa trong form/admin
        verbose_name="Tổng giờ quy đổi",
    )

    class Meta:
        verbose_name_plural = "12. Quản lý NCKH"

    def calc_hours(self):
        if self.category:
            return (self.quantity or 0) * (self.category.default_hours_per_unit or 0)
        return 0.0

    def save(self, *args, **kwargs):
        # Luôn tự tính lại, không dùng giá trị nhập tay
        self.hours = self.calc_hours()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.topic_name

class ResearchMember(models.Model):
    ROLE_CHOICES = (
        ("CN", "Chủ nhiệm"),
        ("CS", "Cộng sự"),
    )

    project = models.ForeignKey(
        ResearchProject,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="Đề tài",
    )
    instructor = models.ForeignKey(
        Instructor,
        on_delete=models.CASCADE,
        related_name="research_memberships",
        verbose_name="Giảng viên",
    )
    role = models.CharField(
        max_length=2,
        choices=ROLE_CHOICES,
        default="CN",
        verbose_name="Vai trò",
    )
    order = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Thứ tự trong đề tài",
        help_text="1 = Chủ nhiệm, 2 = CS1, 3 = CS2...",
    )
    share_ratio = models.FloatField(
        default=0,
        verbose_name="Tỷ lệ giờ được hưởng (0–1)",
        help_text="VD: 0.6 = 60%. Nếu để 0 hệ thống sẽ tự chia theo quy tắc 6:4, 4:3:3, 4:2:2:2...",
    )

    class Meta:
        verbose_name_plural = "12.1 Thành viên đề tài NCKH"
        unique_together = ("project", "instructor")

    def __str__(self):
        return f"{self.project.topic_name} - {self.instructor.name}"


class EnterpriseInternship(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, verbose_name="Giảng viên")
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Năm học")
    hours = models.FloatField(default=0, verbose_name="Số giờ TTDN")
    enterprise_name = models.CharField(max_length=255, verbose_name="Đơn vị doanh nghiệp")

    class Meta:
        verbose_name_plural = "13. Quản lý TTDN"

    def __str__(self):
        return self.enterprise_name

class ProfessionalDevelopment(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, verbose_name="Giảng viên")
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="Năm học")
    hours = models.FloatField(default=0, verbose_name="Số giờ Bồi dưỡng")
    content = models.CharField(max_length=255, verbose_name="Nội dung bồi dưỡng")

    class Meta:
        verbose_name_plural = "14. Quản lý Bồi dưỡng"

    def __str__(self):
        return self.content

# ==================================================
# 7. THI - COI THI - CHẤM THI
# ==================================================

class ExamBatch(models.Model):
    """
    Đợt thi tập trung trong 1 Học kỳ.
    Ví dụ: Thi kết thúc HK1 - Đợt 1, Thi giữa kỳ - Đợt 2...
    """
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="exam_batches",
        verbose_name="Học kỳ",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Tên đợt thi",
        help_text="VD: Thi kết thúc HK1 - Đợt 1",
    )
    start_date = models.DateField(verbose_name="Từ ngày",null=True, blank=True) #mới thêm blank với null
    end_date = models.DateField(verbose_name="Đến ngày",null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "17. Đợt thi (ExamBatch)"
        ordering = ["semester", "start_date"]

    def __str__(self):
        return f"{self.name} - {self.semester}"


class ExamSession(models.Model):
    """
    Ca thi cụ thể cho 1 Lớp học phần.
    - Gắn với 1 LHP (CourseSection)
    - Có thể gắn vào 1 Đợt thi (ExamBatch)
    - Phân công Giám thị 1 (thường là GV dạy) và Giám thị 2
    """
    course_section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name="exam_sessions",
        verbose_name="Lớp học phần",
    )
    batch = models.ForeignKey(
        ExamBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_sessions",
        verbose_name="Đợt thi",
    )
    exam_date = models.DateField(verbose_name="Ngày thi")
    start_time = models.TimeField(verbose_name="Giờ bắt đầu",null=True, blank=True) #mới thêm blank với null
    end_time = models.TimeField(verbose_name="Giờ kết thúc",null=True, blank=True) #mới thêm blank với null

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Phòng thi",
    )

    # Giám thị 1 (thường là GV dạy)
    main_supervisor = models.ForeignKey(
        Instructor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="main_exam_sessions",
        verbose_name="Giám thị chính",
    )
    # Giám thị 2 (không nhất thiết là người dạy)
    assistant_supervisor = models.ForeignKey(
        Instructor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistant_exam_sessions",
        verbose_name="Giám thị phụ",
    )

    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "18. Ca thi (ExamSession)"
        ordering = ["exam_date", "start_time"]

    def __str__(self):
        return f"Thi {self.course_section.code} - {self.exam_date}"


class MarkingSession(models.Model):
    """
    Phiên chấm thi cho 1 Ca thi (thường chỉ dùng cho môn TH trên máy).
    - Với môn TN/TL/BC: chấm ngay khi coi thi -> không cần MarkingSession.
    """
    exam_session = models.OneToOneField(
        ExamSession,
        on_delete=models.CASCADE,
        related_name="marking_session",
        verbose_name="Ca thi",
    )
    planned_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ngày dự kiến chấm",
        help_text="Thường sau ngày thi 1-2 tuần.",
    )
    deadline_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Hạn chót nộp điểm",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        verbose_name_plural = "19. Phiên chấm thi (MarkingSession)"

    def __str__(self):
        return f"Chấm thi {self.exam_session}"


class MarkingDuty(models.Model):
    """
    Phân công giảng viên chấm thi trong 1 Phiên chấm.
    Có thể có 1 hoặc nhiều người (Giám khảo 1, Giám khảo 2, cộng sự...).
    """
    ROLE_CHOICES = [
        ("GK1", "Giám khảo 1 (chính, thường là GV dạy)"),
        ("GK2", "Giám khảo 2"),
        ("PHU", "Cộng sự / hỗ trợ"),
    ]

    session = models.ForeignKey(
        MarkingSession,
        on_delete=models.CASCADE,
        related_name="duties",
        verbose_name="Phiên chấm",
    )
    instructor = models.ForeignKey(
        Instructor,
        on_delete=models.CASCADE,
        verbose_name="Giảng viên",
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="GK1",
        verbose_name="Vai trò",
    )
    hours = models.FloatField(
        default=0,
        verbose_name="Giờ chấm quy đổi",
        help_text="Nếu muốn cộng giờ chấm thi vào khối lượng GV thì điền ở đây.",
    )

    class Meta:
        verbose_name_plural = "20. Phân công chấm thi (MarkingDuty)"

    def __str__(self):
        return f"{self.instructor} - {self.get_role_display()} - {self.session}"

# Nếu sau này bạn muốn phân công nhiều giám thị hơn 2 người, mình có thể thêm bảng ExamDuty kiểu:
# class ExamDuty(models.Model):
#     session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name="duties")
#     instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE)
#     role = models.CharField(max_length=20, choices=[("GT1","Giám thị 1"), ("GT2","Giám thị 2"), ("TS","Thư ký"), ...])
#     hours = models.FloatField(default=0, verbose_name="Giờ coi thi quy đổi")
