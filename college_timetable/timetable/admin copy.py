from django.contrib import admin
from .models import (
    AcademicYear, Semester, SemesterBreak, PublicHoliday, SemesterWeek, PeriodSlot,
    TrainingLevel, Department, SpecializationGroup, Major, Curriculum, CurriculumSubject,
    RoomType, Room, RoomCapability,
    Subject, SubjectChapter, AssessmentComponent,
    StudentClass,
    InstructorRole, Instructor, InstructorCompetency, InstructorAvailability,InstructorDuty,WorkloadReductionType,
    CourseSection, TeachingSlot,
    ExamSession, ExamInvigilationAssignment, ExamGradingAssignment,
    ResearchCategory, ResearchProject, EnterpriseInternship, ProfessionalDevelopment, ResearchMember
)


# ==============================
# 1. TIME CONFIG
# ==============================

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("code", "note")
    search_fields = ("code",)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("code", "academic_year", "name", "start_date", "weeks")
    list_filter = ("academic_year",)
    search_fields = ("code", "name")


@admin.register(SemesterBreak)
class SemesterBreakAdmin(admin.ModelAdmin):
    list_display = ("name", "semester", "start_date", "end_date")
    list_filter = ("semester",)


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "is_recurring")
    list_filter = ("is_recurring",)


@admin.register(SemesterWeek)
class SemesterWeekAdmin(admin.ModelAdmin):
    list_display = ("semester", "index", "start_date", "end_date", "is_break")
    list_filter = ("semester", "is_break")
    ordering = ("semester", "index")


@admin.register(PeriodSlot)
class PeriodSlotAdmin(admin.ModelAdmin):
    list_display = ("index", "start_time", "end_time")
    ordering = ("index",)


# ==============================
# 2. CATALOGS
# ==============================

@admin.register(TrainingLevel)
class TrainingLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "form", "duration_semesters")
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(SpecializationGroup)
class SpecializationGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


# ==============================
# 3. MAJOR, CURRICULUM
# ==============================

class CurriculumSubjectInline(admin.TabularInline):
    model = CurriculumSubject
    extra = 1


@admin.register(Major)
class MajorAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "department", "total_semesters")
    list_filter = ("level", "department")
    search_fields = ("code", "name")


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ("major", "intake_year", "name")
    list_filter = ("major", "intake_year")
    inlines = [CurriculumSubjectInline]


# ==============================
# 4. SUBJECT & STRUCTURE
# ==============================

class SubjectChapterInline(admin.TabularInline):
    model = SubjectChapter
    extra = 0


class AssessmentComponentInline(admin.TabularInline):
    model = AssessmentComponent
    extra = 0


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


class RoomCapabilityInline(admin.TabularInline):
    model = RoomCapability
    extra = 0


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "room_type", "capacity")
    list_filter = ("room_type",)
    search_fields = ("code", "name")
    inlines = [RoomCapabilityInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "subject_type", "major",
        "managing_department", "total_periods", "max_class_size",
        "required_room_type", "specialization_group", "is_external_managed"
    )
    list_filter = ("subject_type", "managing_department", "required_room_type")
    search_fields = ("code", "name")
    inlines = [SubjectChapterInline, AssessmentComponentInline]


# ==============================
# 5. STUDENT CLASS
# ==============================

@admin.register(StudentClass)
class StudentClassAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "size", "major", "academic_year", "department", "homeroom_teacher")
    list_filter = ("major", "academic_year", "department")
    search_fields = ("code", "name")


# ==============================
# 6. INSTRUCTORS
# ==============================

class InstructorCompetencyInline(admin.TabularInline):
    model = InstructorCompetency
    extra = 0


@admin.register(InstructorRole)
class InstructorRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "workload_reduction")


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "department",
        "teaching_quota", "admin_quota",
        "max_subjects_per_semester", "is_leader"
    )
    list_filter = ("department", "is_leader", "roles")
    search_fields = ("code", "name")
    filter_horizontal = ("roles", "allowed_majors")
    inlines = [InstructorCompetencyInline]


@admin.register(InstructorAvailability)
class InstructorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("instructor", "day_of_week", "start_period", "end_period", "is_available")
    list_filter = ("instructor", "day_of_week", "is_available")



# @admin.register(InstructorDuty)
# class InstructorDutyAdmin(admin.ModelAdmin):
#     list_display = ("instructor", "academic_year", "name", "reduction_percent")
#     list_filter = ("academic_year", "name")
#     search_fields = ("instructor__name", "instructor__code", "name")

@admin.register(WorkloadReductionType)
class WorkloadReductionTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "teaching_reduction_percent", "admin_reduction_percent")
    search_fields = ("code", "name")

@admin.register(InstructorDuty)
class InstructorDutyAdmin(admin.ModelAdmin):
    list_display = ("instructor", "academic_year", "reduction_type", "months")
    list_filter = ("academic_year", "reduction_type")
    search_fields = ("instructor__name", "instructor__code")
# ==============================
# 7. COURSE SECTION & TIMETABLE
# ==============================


class TeachingSlotInline(admin.TabularInline):
    model = TeachingSlot
    extra = 0
    filter_horizontal = ("weeks",)   # chọn nhiều tuần cho 1 slot trong inline

@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = (
        "code", "subject", "semester", "instructor",
        "planned_periods", "start_week", "week_count",
        "sessions_per_week", "is_locked"
    )
    list_filter = ("semester", "subject__subject_type", "instructor")
    search_fields = ("code", "subject__name")
    filter_horizontal = ("classes",)
    inlines = [TeachingSlotInline]

@admin.register(TeachingSlot)
class TeachingSlotAdmin(admin.ModelAdmin):
    list_display = (
        "course_section",
        "day_of_week",
        "start_period",
        "end_period",
        "room",
        "week_list",      # ← thêm cột hiển thị tuần
        "is_locked",
    )
    list_filter = ("course_section__semester", "day_of_week", "room")
    search_fields = ("course_section__code",)
    filter_horizontal = ("weeks",)   # khi sửa 1 slot, chọn tuần kiểu multi-select cho dễ

    def week_list(self, obj):
        # In ra danh sách tuần dạng: 1, 2, 3, 4...
        return ", ".join(str(w.index) for w in obj.weeks.order_by("index"))
    week_list.short_description = "Tuần"


# ==============================
# 8. EXAMS
# ==============================

class ExamInvigilationAssignmentInline(admin.TabularInline):
    model = ExamInvigilationAssignment
    extra = 0


class ExamGradingAssignmentInline(admin.TabularInline):
    model = ExamGradingAssignment
    extra = 0


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ("course_section", "component", "date", "start_time", "duration_minutes", "room")
    list_filter = ("course_section__semester", "date", "room")
    search_fields = ("course_section__code", "component__name")
    inlines = [ExamInvigilationAssignmentInline, ExamGradingAssignmentInline]


@admin.register(ExamInvigilationAssignment)
class ExamInvigilationAssignmentAdmin(admin.ModelAdmin):
    list_display = ("exam_session", "instructor", "role")
    list_filter = ("role", "instructor")


@admin.register(ExamGradingAssignment)
class ExamGradingAssignmentAdmin(admin.ModelAdmin):
    list_display = ("exam_session", "instructor", "role", "start_date", "end_date")
    list_filter = ("role", "instructor")


# ==============================
# 9. OTHER WORKLOAD
# ==============================

@admin.register(ResearchProject)
class ResearchProjectAdmin(admin.ModelAdmin):
    list_display = ("topic_name", "year", "category", "quantity", "hours")
    list_filter = ("year", "category")
    search_fields = ("topic_name",)
    readonly_fields = ("hours",)  # chỉ cho xem, không cho sửa



@admin.register(ResearchMember)
class ResearchMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "instructor", "role", "order", "share_ratio")
    list_filter = ("project__year", "role")
    search_fields = ("project__topic_name", "instructor__name", "instructor__code")

@admin.register(EnterpriseInternship)
class EnterpriseInternshipAdmin(admin.ModelAdmin):
    list_display = ("enterprise_name", "instructor", "year", "hours")
    list_filter = ("year", "instructor")


@admin.register(ProfessionalDevelopment)
class ProfessionalDevelopmentAdmin(admin.ModelAdmin):
    list_display = ("content", "instructor", "year", "hours")
    list_filter = ("year", "instructor")



@admin.register(ResearchCategory)
class ResearchCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "unit_label", "default_hours_per_unit")
    search_fields = ("code", "name")



