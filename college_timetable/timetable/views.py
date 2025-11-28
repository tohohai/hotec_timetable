from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.contrib import messages
from .forms import ExcelUploadForm
from . import import_services

import csv

def home(request):
    return render(request, "timetable/home.html")

from .models import (
    AcademicYear,
    CourseSection,
    Instructor,   
    Room,
    ResearchMember,
    StudentClass,
    TeachingSlot,   
    WorkloadReductionType
)
from .forms import (
    SemesterChoiceForm,
    SemiAutoScheduleForm,
    ClassTimetableForm,
    InstructorTimetableForm,
    RoomTimetableForm,
    InstructorWorkloadForm,
)

from .services import (
    auto_schedule_whole_semester_fixed,
    semi_auto_schedule_section,
    calculate_instructor_workload,
)

from .services import (
    auto_schedule_whole_semester_fixed,
    semi_auto_schedule_section,
)
# Các thứ trong tuần & tiết (dùng cho bảng TKB)
DAYS = [
    (1, "Thứ 2"),
    (2, "Thứ 3"),
    (3, "Thứ 4"),
    (4, "Thứ 5"),
    (5, "Thứ 6"),
    (6, "Thứ 7"),
]

# Giả sử tối đa 10 tiết / ngày
PERIODS = list(range(1, 15))

def build_timetable_grid(slots):
    """
    slots: queryset TeachingSlot đã lọc theo lớp và học kỳ.
    Trả về dict:
        grid[(day, period)] = list các slot rơi vào ô đó (thường 0 hoặc 1)
    """
    grid = {(day, p): [] for day, _ in DAYS for p in PERIODS}

    for s in slots:
        for p in range(s.start_period, s.end_period + 1):
            key = (s.day_of_week, p)
            if key in grid:
                grid[key].append(s)

    return grid

def semester_overview(request): 
    """
    Trang chọn Học kỳ + Khoa, hiển thị danh sách Lớp học phần.
    Có nút chạy auto_schedule cho cả học kỳ.
    """
    sections = None
    semester = None
    department_code = None
    auto_result = None

    if request.method == "POST":
        form = SemesterChoiceForm(request.POST)
        if form.is_valid():
            semester = form.cleaned_data["semester"]
            department_code = form.cleaned_data["department_code"]

            # Nếu bấm nút auto_schedule
         
            if "run_auto" in request.POST:
                ok, fail = auto_schedule_whole_semester_fixed(
                    semester,
                    department_code=department_code,
                    reset_existing=True,   # xoá slot cũ trước khi xếp lại
                )
                auto_result = {
                    "ok_count": len(ok),
                    "fail_count": len(fail),
                    "fail": fail,
                }


            sections = CourseSection.objects.filter(
                semester=semester,
                classes__department__code=department_code,
            ).distinct().select_related("subject", "instructor")
    else:
        form = SemesterChoiceForm()

    context = {
        "form": form,
        "semester": semester,
        "department_code": department_code,
        "sections": sections,
        "auto_result": auto_result,
    }
    return render(request, "timetable/semester_overview.html", context)

def section_schedule(request, pk):
    """
    Trang xếp bán tự động cho MỘT lớp học phần.
    Cho phép chọn:
      - Tuần bắt đầu
      - Số buổi/tuần
      - Số tuần (option)
      - Danh sách phòng được dùng
    """
    section = get_object_or_404(CourseSection, pk=pk)

    if request.method == "POST":
        form = SemiAutoScheduleForm(request.POST)
        # Cập nhật queryset cho allowed_rooms mỗi lần (quan trọng)
        form.fields["allowed_rooms"].queryset = Room.objects.all()

        if form.is_valid():
            start_week_index = form.cleaned_data["start_week_index"]
            sessions_per_week = form.cleaned_data["sessions_per_week"]
            weeks_count = form.cleaned_data["weeks_count"]
            allowed_rooms_qs = form.cleaned_data["allowed_rooms"]

            allowed_codes = None
            if allowed_rooms_qs:
                allowed_codes = list(allowed_rooms_qs.values_list("code", flat=True))

            slots, error = semi_auto_schedule_section(
                section=section,
                start_week_index=start_week_index,
                sessions_per_week=sessions_per_week,
                weeks_count=weeks_count,
                allowed_room_codes=allowed_codes,
            )

            # Lấy lại các slot hiện tại để hiển thị
            current_slots = TeachingSlot.objects.filter(course_section=section).prefetch_related("weeks", "room")

            return render(
                request,
                "timetable/section_schedule.html",
                {
                    "section": section,
                    "form": form,
                    "created_slots": slots,
                    "error": error,
                    "current_slots": current_slots,
                },
            )
    else:
        form = SemiAutoScheduleForm()
        form.fields["allowed_rooms"].queryset = Room.objects.all()

    current_slots = TeachingSlot.objects.filter(course_section=section).prefetch_related("weeks", "room")

    return render(
        request,
        "timetable/section_schedule.html",
        {
            "section": section,
            "form": form,
            "created_slots": None,
            "error": None,
            "current_slots": current_slots,
        },
    )

def section_list(request):
    """
    Danh sách Lớp học phần, để sau này chọn vào xếp bán tự động / chỉnh tay.
    """
    sections = CourseSection.objects.select_related(
        "subject", "semester", "student_class", "instructor"
    ).order_by("semester__start_date", "code")

    return render(request, "timetable/section_list.html", {
        "sections": sections,
    })

def class_timetable_view(request):
    """
    Xem thời khóa biểu theo Lớp sinh viên, cho 1 Học kỳ.
    """
    form = ClassTimetableForm(request.GET or None)

    grid_rows = None
    selected_class = None
    semester = None
    slots = None

    if form.is_valid():
        semester = form.cleaned_data["semester"]
        selected_class = form.cleaned_data["student_class"]

        # Lấy tất cả slot của lớp này trong học kỳ đó
        slots = TeachingSlot.objects.filter(
            course_section__semester=semester,
            course_section__classes=selected_class,
        ).select_related(
            "course_section__subject",
            "course_section__instructor",
            "room",
        ).prefetch_related("weeks", "course_section__classes").order_by(
            "day_of_week", "start_period"
        )

        # Dựng lưới
        grid = build_timetable_grid(slots)

        # Chuẩn bị dữ liệu thân thiện cho template
        grid_rows = []
        for p in PERIODS:
            row = {"period": p, "cells": []}
            for day_val, day_label in DAYS:
                cell_slots = grid.get((day_val, p), [])
                row["cells"].append(cell_slots)
            grid_rows.append(row)

    context = {
        "form": form,
        "grid_rows": grid_rows,
        "days": DAYS,
        "selected_class": selected_class,
        "semester": semester,
    }
    return render(request, "timetable/class_timetable.html", context)

def room_timetable_view(request):
    """
    Xem thời khóa biểu theo PHÒNG học, cho 1 Học kỳ.
    """
    form = RoomTimetableForm(request.GET or None)

    grid_rows = None
    room = None
    semester = None
    slots = None

    if form.is_valid():
        semester = form.cleaned_data["semester"]
        room = form.cleaned_data["room"]

        # Lấy tất cả slot trong phòng này ở học kỳ đó
        slots = TeachingSlot.objects.filter(
            course_section__semester=semester,
            room=room,
        ).select_related(
            "course_section__subject",
            "course_section__instructor",
            "room",
        ).prefetch_related("weeks", "course_section__classes").order_by(
            "day_of_week", "start_period"
        )

        grid = build_timetable_grid(slots)

        grid_rows = []
        for p in PERIODS:
            row = {"period": p, "cells": []}
            for day_val, day_label in DAYS:
                cell_slots = grid.get((day_val, p), [])
                row["cells"].append(cell_slots)
            grid_rows.append(row)

    context = {
        "form": form,
        "grid_rows": grid_rows,
        "days": DAYS,
        "room": room,
        "semester": semester,
    }
    return render(request, "timetable/room_timetable.html", context)

def build_timetable_grid(slots):
    """
    slots: queryset TeachingSlot đã filter theo lớp hoặc theo GV và theo Học kỳ.
    Trả về:
        grid[(day, period)] = list các slot rơi vào ô đó (thường 0 hoặc 1)
    """
    grid = {(day, p): [] for day, _ in DAYS for p in PERIODS}

    for s in slots:
        for p in range(s.start_period, s.end_period + 1):
            if (s.day_of_week, p) in grid:
                grid[(s.day_of_week, p)].append(s)

    return grid

def instructor_timetable_view(request):
    """
    Xem thời khóa biểu theo GIẢNG VIÊN, cho 1 Học kỳ.
    """
    form = InstructorTimetableForm(request.GET or None)

    grid_rows = None
    instructor = None
    semester = None
    slots = None

    if form.is_valid():
        semester = form.cleaned_data["semester"]
        instructor = form.cleaned_data["instructor"]

        # Lấy tất cả slot của GV này trong học kỳ
        slots = TeachingSlot.objects.filter(
            course_section__semester=semester,
            course_section__instructor=instructor,
        ).select_related(
            "course_section__subject",
            "room",
        ).prefetch_related("weeks", "course_section__classes").order_by(
            "day_of_week", "start_period"
        )

        grid = build_timetable_grid(slots)

        grid_rows = []
        for p in PERIODS:
            row = {"period": p, "cells": []}
            for day_val, day_label in DAYS:
                cell_slots = grid.get((day_val, p), [])
                row["cells"].append(cell_slots)
            grid_rows.append(row)

    context = {
        "form": form,
        "grid_rows": grid_rows,
        "days": DAYS,
        "instructor": instructor,
        "semester": semester,
    }
    return render(request, "timetable/instructor_timetable.html", context)

def instructor_workload_view(request):
    form = InstructorWorkloadForm(request.GET or None)
    academic_year = None
    workload_data = []  # luôn là list
    reduction_types = list(WorkloadReductionType.objects.all().order_by("code"))

    if form.is_valid():
        academic_year = form.cleaned_data["academic_year"]
        workload_data = calculate_instructor_workload(academic_year)

        # Tính giờ giảm theo từng loại miễn giảm cho mỗi GV
        for row in workload_data:
            per_type_list = []
            duty_breakdown = row.get("duty_breakdown", [])

            for rt in reduction_types:
                hours = 0.0
                for b in duty_breakdown:
                    if b["obj"].reduction_type_id == rt.id:
                        hours += b["teaching_hours"]
                per_type_list.append({
                    "type": rt,
                    "hours": hours,
                })

            row["teaching_reduction_by_type"] = per_type_list

    context = {
        "form": form,
        "academic_year": academic_year,
        "workload_data": workload_data,
        "reduction_types": reduction_types,
    }
    return render(request, "timetable/instructor_workload.html", context)

def instructor_workload_detail(request, instructor_id, year_id):
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    instructor = get_object_or_404(Instructor, id=instructor_id)

    # Dùng lại hàm tính chung, rồi lọc đúng 1 GV
    all_data = calculate_instructor_workload(academic_year)
    row = None
    for r in all_data:
        if r["instructor"].id == instructor.id:
            row = r
            break

    # Nếu chưa có dòng (GV mới, chưa có gì) -> tạo row rỗng
    if row is None:
        row = {
            "instructor": instructor,
            "duties": [],
            "duty_breakdown": [],
            "base_teaching_quota": instructor.teaching_quota or 0,
            "base_admin_quota": instructor.admin_quota or 0,
            "teaching_reduced_hours": 0.0,
            "admin_reduced_hours": 0.0,
            "teaching_quota_adj": instructor.teaching_quota or 0,
            "admin_quota_adj": instructor.admin_quota or 0,
            "teaching_hours": 0.0,
            "teaching_overload": 0.0,
            "admin_hours_total": 0.0,
            "admin_overload": 0.0,
            "rp_hours": 0.0,
            "ei_hours": 0.0,
            "pd_hours": 0.0,
            "teaching_to_admin_hours": 0.0,
        }

    # Lấy danh sách đề tài NCKH chi tiết cho GV này
    research_members = ResearchMember.objects.filter(
        instructor=instructor,
        project__year=academic_year,
    ).select_related("project", "project__category").order_by("project__topic_name")

    context = {
        "academic_year": academic_year,
        "instructor": instructor,
        "row": row,
        "research_members": research_members,
    }
    return render(request, "timetable/instructor_workload_detail.html", context)


IMPORT_CONFIG = {
    "departments": {
        "label": "Khoa (Department)",
        "function": import_services.import_departments_from_excel,
        "columns": ["code", "name"],
        "description": "Danh sách Khoa quản lý.",
    },
    "training_levels": {
        "label": "Bậc đào tạo (TrainingLevel)",
        "function": import_services.import_training_levels_from_excel,
        "columns": ["code", "name", "form"],
        "description": "VD: Cao đẳng, Trung cấp...",
    },
    "academic_years": {
        "label": "Năm học (AcademicYear)",
        "function": import_services.import_academic_years_from_excel,
        "columns": ["code"],
        "description": "VD: 2025, 2025-2026...",
    },
    "semesters": {
        "label": "Học kỳ (Semester)",
        "function": import_services.import_semesters_from_excel,
        "columns": ["academic_year_code", "code", "name", "start_date", "weeks"],
        "description": "HK1, HK2... với ngày bắt đầu & số tuần.",
    },
    "room_types": {
        "label": "Loại phòng (RoomType)",
        "function": import_services.import_roomtypes_from_excel,
        "columns": ["code", "name"],
        "description": "LT, TH, ONLINE, SÂN...",
    },
    "specialization_groups": {
        "label": "Nhóm chuyên môn (SpecializationGroup)",
        "function": import_services.import_specialization_groups_from_excel,
        "columns": ["code", "name"],
        "description": "Nhóm ngành, nhóm môn thực hành...",
    },
    "rooms": {
        "label": "Phòng học (Room)",
        "function": import_services.import_rooms_from_excel,
        "columns": ["code", "name", "room_type_code", "specialization_group_codes"],
        "description": "Phòng Lý thuyết / Thực hành / Online...",
    },
    "majors": {
        "label": "Ngành (Major)",
        "function": import_services.import_majors_from_excel,
        "columns": ["code", "name", "level_code", "department_code", "is_general", "total_credits", "total_semesters"],
        "description": "Ngành Cao đẳng/Trung cấp CNTT...",
    },
    "instructors": {
        "label": "Giảng viên (Instructor)",
        "function": import_services.import_instructors_from_excel,
        "columns": ["code", "name", "department_code", "is_leader", "teaching_quota", "admin_quota", "conversion_ratio"],
        "description": "Danh sách Giảng viên khoa.",
    },
    "student_classes": {
        "label": "Lớp sinh viên (StudentClass)",
        "function": import_services.import_student_classes_from_excel,
        "columns": ["code", "name", "size", "major_code", "academic_year_code", "homeroom_teacher_code"],
        "description": "Các lớp K25..., sĩ số, GVCN...",
    },
    "subjects": {
        "label": "Môn học (Subject)",
        "function": import_services.import_subjects_from_excel,
        "columns": ["code", "name", "major_code", "department_code", "required_room_type_code", "specialization_group_code", "total_periods", "form", "semester_index"],
        "description": "Danh mục môn dùng để xếp TKB.",
    },
}


def data_import_menu(request):
    """Trang liệt kê các loại dữ liệu có thể import."""
    return render(request, "timetable/data_import_menu.html", {
        "import_config": IMPORT_CONFIG,
    })


def data_import_view(request, data_type):
    config = IMPORT_CONFIG.get(data_type)
    if not config:
        messages.error(request, "Loại dữ liệu không hợp lệ.")
        return redirect("timetable:data_import_menu")

    form = ExcelUploadForm(request.POST or None, request.FILES or None)
    result = None

    if request.method == "POST" and form.is_valid():
        file = form.cleaned_data["file"]
        import_func = config["function"]
        created, updated, errors = import_func(file)
        result = {
            "created": created,
            "updated": updated,
            "errors": errors,
        }
        if not errors:
            messages.success(request, f"Import thành công! Tạo mới {created}, cập nhật {updated}.")
        else:
            messages.warning(request, f"Tạo mới {created}, cập nhật {updated}, có {len(errors)} lỗi.")

    return render(request, "timetable/data_import_view.html", {
        "config": config,
        "data_type": data_type,
        "form": form,
        "result": result,
    })

def timetable_by_class(request):
    """
    TKB theo Lớp sinh viên.
    Tạm thời hiển thị trang trống / đang xây dựng.
    Sau này mình sẽ fill logic ở đây.
    """
    return render(request, "timetable/timetable_by_class.html")


def timetable_by_room(request):
    """
    TKB theo Phòng học.
    """
    return render(request, "timetable/timetable_by_room.html")


def timetable_by_instructor(request):
    """
    TKB theo Giảng viên.
    """
    return render(request, "timetable/timetable_by_instructor.html")
