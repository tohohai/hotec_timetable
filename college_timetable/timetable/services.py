from math import ceil
from django.db.models import Q
from datetime import timedelta
from django.db import models
from .models import (    
    AcademicYear,    
    CourseSection,  
    Curriculum,
    CurriculumSubject,  
    EnterpriseInternship,
    Instructor,
    InstructorAvailability,    
    InstructorDuty,
    ProfessionalDevelopment,
    Room,
    ResearchProject,
    ResearchMember,
    StudentClass,
    Semester,
    SemesterWeek,
    Subject,
    TeachingSlot,   
)

ACADEMIC_YEAR_MONTHS = 10  # hoặc 12 nếu bạn muốn tính theo năm dương lịch


def suggest_share_weights(num_members: int):
    """
    Trả về list trọng số (tổng khoảng 10) theo số người.
    Sau đó sẽ chuẩn hóa thành tỷ lệ (0–1).
    """
    if num_members <= 0:
        return []
    if num_members == 1:
        return [10]
    if num_members == 2:
        return [6, 4]          # 6:4
    if num_members == 3:
        return [4, 3, 3]       # 4:3:3
    if num_members == 4:
        return [4, 2, 2, 2]    # 4:2:2:2
    if num_members == 5:
        return [3, 2, 2, 2, 1]
    if num_members == 6:
        return [3, 2, 2, 1, 1, 1]
    base = 10 / num_members
    return [base] * num_members

def auto_distribute_research_members(project: ResearchProject):
    members = list(project.members.order_by("order", "id"))
    n = len(members)
    if n == 0:
        return

    weights = suggest_share_weights(n)
    total_weight = sum(weights) or 1
    for m, w in zip(members, weights):
        m.share_ratio = w / total_weight  # ví dụ 6/10 = 0.6
        m.save()

def get_semester_index_for_class(student_class: StudentClass, semester: Semester) -> int:
    """
    Xác định 'học kỳ thứ mấy' trong CTĐT của một lớp tại một Học kỳ cụ thể.

    Ví dụ bạn đã nói:
      - HK1 năm học 2025 thì:
          + Khoá 25 (năm nhập học 2025)  -> HK1
          + Khoá 24 (năm nhập học 2024)  -> HK3
          + Khoá 23 (năm nhập học 2023)  -> HK5

    Ở đây mình viết 1 version MINH HOẠ,
    bạn chỉ cần chỉnh lại phần parse năm/khoá cho đúng format thật sự.
    """

    # Giả sử AcademicYear.code là số năm, ví dụ '2025', '2024'...
    try:
        cur_year = int(semester.academic_year.code)
        intake_year = int(student_class.academic_year.code)
    except ValueError:
        # Nếu code không phải số (vd: 'NH25-26'), bạn sửa logic này lại.
        raise ValueError(
            f"Chưa cài đặt logic tính semester_index cho dạng mã năm học: "
            f"{semester.academic_year.code} / {student_class.academic_year.code}"
        )

    # Chênh lệch năm tuyển so với năm hiện tại
    # VD: intake 2025, current 2025 -> diff = 0 -> HK1
    #     intake 2024, current 2025 -> diff = 1 -> HK3
    #     intake 2023, current 2025 -> diff = 2 -> HK5
    year_diff = cur_year - intake_year

    # Mặc định mỗi năm 2 học kỳ.
    # Giả sử HK1 là học kỳ lẻ: 1,3,5; HK2 là học kỳ chẵn: 2,4,6.
    if semester.code.upper() in ("HK1", "1"):
        # HK lẻ: 1 + 2*diff
        return 1 + 2 * year_diff
    elif semester.code.upper() in ("HK2", "2"):
        # HK chẵn: 2 + 2*diff
        return 2 + 2 * year_diff
    else:
        # Nếu dùng code khác (VD: 'HK3', 'Hè'...), bạn xử lý thêm.
        raise ValueError(f"Không hiểu mã Học kỳ: {semester.code}")


def generate_course_sections_for_semester(semester: Semester, department_code: str = "CNTT"):
    """
    Sinh Lớp học phần (CourseSection) cho một Học kỳ:

    - Lọc các Lớp sinh viên thuộc khoa cần xếp (mặc định: CNTT).
    - Với mỗi lớp:
        + Tìm Curriculum (Ngành + Khoá/Năm nhập học).
        + Tính 'semester_index' theo quy tắc trên.
        + Lấy các CurriculumSubject đúng semester_index.
        + Bỏ qua môn is_external_managed (môn do khoa khác xếp).
        + Dựa vào sĩ số lớp & Subject.max_class_size để chia số lớp HP.
        + Tạo CourseSection tương ứng, gán lớp & planned_periods.
    """
    classes = StudentClass.objects.filter(department__code=department_code)

    created_sections = []

    for cls in classes:
        # 1. Xác định CTĐT của lớp
        try:
            curriculum = Curriculum.objects.get(major=cls.major, intake_year=cls.academic_year)
        except Curriculum.DoesNotExist:
            # Không có CTĐT -> bỏ qua lớp này
            continue

        # 2. Xác định học kỳ trong CTĐT mà lớp đang học
        semester_index = get_semester_index_for_class(cls, semester)

        # 3. Lấy các môn sẽ học trong học kỳ này
        cur_subjects = CurriculumSubject.objects.filter(
            curriculum=curriculum,
            semester_index=semester_index
        ).select_related("subject")

        for cs in cur_subjects:
            subject: Subject = cs.subject

            # Nếu môn do đơn vị khác xếp thì bỏ qua
            if subject.is_external_managed:
                continue

            # Tổng tiết cho môn này
            total_periods = cs.total_periods or subject.total_periods

            # Sĩ số lớp và sĩ số tối đa/lớp HP
            max_size = subject.max_class_size or 35
            num_sections = ceil(cls.size / max_size)

            for i in range(1, num_sections + 1):
                section_code = f"{cls.code}_{subject.code}_{i:02d}"

                course_section, created = CourseSection.objects.get_or_create(
                    semester=semester,
                    code=section_code,
                    defaults={
                        "subject": subject,
                        "planned_periods": total_periods,
                    },
                )
                # Gắn class vào (nếu sau này bạn cho gộp lớp, có thể thay đổi logic ở đây)
                course_section.classes.add(cls)

                created_sections.append(course_section)

    return created_sections

# ================
# HELPER TOOL
# ================

def get_weeks_for_section(section: CourseSection, semester: Semester):
    """
    Lấy danh sách SemesterWeek mà Lớp học phần này sẽ dạy:
    - Bỏ các tuần is_break=True
    - Áp dụng start_week, week_count nếu có
    """
    qs = SemesterWeek.objects.filter(semester=semester, is_break=False).order_by("index")
    weeks = list(qs)

    if not weeks:
        return []

    start_index = section.start_week or weeks[0].index
    # map index -> object
    index_map = {w.index: w for w in weeks}

    # danh sách tuần cho section
    filtered = [w for w in weeks if w.index >= start_index]

    if section.week_count:
        filtered = filtered[: section.week_count]

    return filtered

def periods_per_session_for_subject(section: CourseSection) -> int:
    """
    Xác định số tiết mỗi buổi:
    - Lý thuyết: 5 tiết/buổi
    - Thực hành / Tích hợp: 4 tiết/buổi
    - Thực tập: không xếp phòng, sẽ bỏ qua ở auto_schedule
    """
    stype = section.subject.subject_type
    if stype == "LT":
        return 5
    elif stype in ("TH", "TICH_HOP"):
        return 4
    elif stype == "THUC_TAP":
        return 0
    # mặc định
    return 5

def get_candidate_rooms_for_section(section: CourseSection):
    """
    Lấy danh sách phòng phù hợp cho Lớp học phần (theo loại phòng, sức chứa, chuyên môn).
    Nếu môn là THUC_TAP -> trả [] để slot có thể room=None.
    """
    subject = section.subject
    total_students = sum(cls.size for cls in section.classes.all())

    if subject.subject_type == "THUC_TAP":
        return []

    qs = Room.objects.all()

    # Loại phòng
    if subject.required_room_type:
        qs = qs.filter(room_type=subject.required_room_type)

    # Sức chứa
    qs = qs.filter(capacity__gte=total_students)

    # Nếu môn yêu cầu nhóm chuyên môn, lọc theo capabilities
    if subject.specialization_group:
        qs = qs.filter(capabilities=subject.specialization_group)

    # Nếu phòng có allowed_majors, kiểm tra ít nhất một major của lớp nằm trong đó
    majors = set(cls.major_id for cls in section.classes.all())
    if majors:
        qs = qs.filter(Q(allowed_majors__isnull=True) | Q(allowed_majors__in=majors)).distinct()

    return list(qs)

def time_overlap(a_start, a_end, b_start, b_end) -> bool:
    """Hai đoạn tiết có giao nhau không?"""
    return not (a_end < b_start or b_end < a_start)

def weeks_overlap(weeks_a, weeks_b) -> bool:
    """Hai tập tuần có giao nhau không?"""
    set_a = {w.id for w in weeks_a}
    set_b = {w.id for w in weeks_b}
    return bool(set_a & set_b)

def instructor_is_available(instructor, day_of_week, start_period, end_period):
    """
    Kiểm tra giảng viên có bị đánh dấu 'không rảnh' ở khung giờ này không.
    Nếu không có record nào is_available=False trùng -> coi như rảnh.
    """
    if instructor is None:
        return True

    blocked = InstructorAvailability.objects.filter(
        instructor=instructor,
        day_of_week=day_of_week,
        is_available=False,
        start_period__lte=end_period,
        end_period__gte=start_period,
    ).exists()

    return not blocked

def has_conflict_for_room(room, semester, day_of_week, start_period, end_period, weeks):
    if room is None:
        return False

    slots = TeachingSlot.objects.filter(
        course_section__semester=semester,
        room=room,
        day_of_week=day_of_week,
    ).prefetch_related("weeks")

    for slot in slots:
        if not time_overlap(start_period, end_period, slot.start_period, slot.end_period):
            continue
        if weeks_overlap(weeks, slot.weeks.all()):
            return True

    return False

def has_conflict_for_class(student_classes, semester, day_of_week, start_period, end_period, weeks):
    from .models import StudentClass  # tránh circular import

    class_ids = [c.id for c in student_classes]

    slots = TeachingSlot.objects.filter(
        course_section__semester=semester,
        course_section__classes__in=class_ids,
        day_of_week=day_of_week,
    ).distinct().prefetch_related("weeks")

    for slot in slots:
        if not time_overlap(start_period, end_period, slot.start_period, slot.end_period):
            continue
        if weeks_overlap(weeks, slot.weeks.all()):
            return True

    return False

def has_conflict_for_instructor(instructor, semester, day_of_week, start_period, end_period, weeks):
    if instructor is None:
        return False

    slots = TeachingSlot.objects.filter(
        course_section__semester=semester,
        course_section__instructor=instructor,
        day_of_week=day_of_week,
    ).prefetch_related("weeks")

    for slot in slots:
        if not time_overlap(start_period, end_period, slot.start_period, slot.end_period):
            continue
        if weeks_overlap(weeks, slot.weeks.all()):
            return True

    return False

def auto_schedule(semester: Semester, department_code: str = "CNTT"):
    """
    Xếp TKB tự động cho 1 Học kỳ (phiên bản: 1 buổi/tuần, cố định 1 ngày/giờ/phòng).

    - Mặc định: mỗi LHP có 1 buổi/tuần (sessions_per_week của section hiện tại
      mình sẽ bỏ qua, coi như =1).
    - Mỗi LHP sẽ có:
        + 1 TeachingSlot duy nhất
        + gắn nhiều tuần (weeks)
      => hiển thị ra: 1 dòng, "Tuần: 1,2,3,...".
    """
    from .models import CourseSection, SemesterWeek
    # dùng lại các helper đã có trong file:
    # periods_per_session_for_subject, get_candidate_rooms_for_section,
    # instructor_is_available, has_conflict_for_room,
    # has_conflict_for_class, has_conflict_for_instructor

    # Lấy tất cả LHP thuộc khoa cần xếp
    sections = CourseSection.objects.filter(
        semester=semester,
        classes__department__code=department_code,
    ).distinct().select_related("subject", "instructor").prefetch_related("classes")

    # Lấy tất cả tuần học (không nghỉ) của học kỳ
    all_weeks = list(
        SemesterWeek.objects.filter(
            semester=semester,
            is_break=False
        ).order_by("index")
    )

    if not all_weeks:
        return [], [(None, "Học kỳ không có tuần học (SemesterWeek) nào")]

    scheduled_sections = []
    failed_sections = []

    for section in sections:
        if section.is_locked:
            continue

        subject = section.subject
        per_session = periods_per_session_for_subject(section)

        if per_session == 0:
            # Môn thực tập: không xếp TKB ở đây
            continue

        # Xác định các tuần ứng viên cho LHP này
        start_week_index = section.start_week or all_weeks[0].index

        weeks_candidate = [
            w for w in all_weeks
            if w.index >= start_week_index
        ]

        if section.week_count:
            weeks_candidate = weeks_candidate[: section.week_count]

        if not weeks_candidate:
            failed_sections.append((section, "Không có tuần dạy hợp lệ"))
            continue

        # Tổng tiết của LHP
        total_periods = section.planned_periods or subject.total_periods

        # Số buổi cần thiết
        sessions_needed = ceil(total_periods / per_session)

        # Mặc định: 1 buổi/tuần => cần 'sessions_needed' tuần
        weeks_needed = min(sessions_needed, len(weeks_candidate))
        weeks_for_course = weeks_candidate[:weeks_needed]

        if not weeks_for_course:
            failed_sections.append((section, "Không đủ tuần để xếp môn này"))
            continue

        # Phòng phù hợp
        rooms = get_candidate_rooms_for_section(section)
        if not rooms and subject.subject_type != "THUC_TAP":
            failed_sections.append((section, "Không tìm được phòng phù hợp"))
            continue

        day_candidates = [1, 2, 3, 4, 5, 6]  # Th2..Th7
        start_period_candidates = [1, 6]     # sáng, chiều

        placed = False

        for day in day_candidates:
            if placed:
                break

            for start_p in start_period_candidates:
                end_p = start_p + per_session - 1

                # GV rảnh ở khung này? (không phân biệt tuần)
                if not instructor_is_available(section.instructor, day, start_p, end_p):
                    continue

                room_options = rooms if rooms else [None]

                for room in room_options:
                    # Check trùng phòng / lớp / GV trên toàn bộ weeks_for_course
                    if has_conflict_for_room(room, semester, day, start_p, end_p, weeks_for_course):
                        continue

                    if has_conflict_for_class(section.classes.all(), semester, day, start_p, end_p, weeks_for_course):
                        continue

                    if has_conflict_for_instructor(section.instructor, semester, day, start_p, end_p, weeks_for_course):
                        continue

                    # OK -> tạo 1 slot duy nhất, gắn tất cả tuần
                    slot = TeachingSlot.objects.create(
                        course_section=section,
                        room=room,
                        day_of_week=day,
                        start_period=start_p,
                        end_period=end_p,
                        method="",
                        is_locked=False,
                    )
                    slot.weeks.set(weeks_for_course)

                    scheduled_sections.append(section)
                    placed = True
                    break  # thoát phòng

                if placed:
                    break  # thoát start_period

        if not placed:
            failed_sections.append((section, "Không tìm được (Thứ/Tiết/Phòng) phù hợp cho tất cả các tuần"))

    return scheduled_sections, failed_sections

def semi_auto_schedule_section(
    section: CourseSection,
    start_week_index: int,
    sessions_per_week: int,
    weeks_count: int | None = None,
    allowed_room_codes: list[str] | None = None,
):
    """
    Bán tự động xếp TKB cho MỘT Lớp học phần:

    - section: CourseSection cần xếp
    - start_week_index: bắt đầu từ tuần thứ mấy (VD: 10)
    - sessions_per_week: số buổi/tuần (2 hoặc 3)
    - weeks_count:
        + nếu None: tự tính số tuần cần thiết dựa trên tổng tiết
        + nếu có: dùng đúng số tuần này (VD: 6 tuần)
    - allowed_room_codes:
        + nếu None: dùng tất cả phòng phù hợp
        + nếu list: chỉ dùng các phòng có code trong list

    Trả về:
        (created_slots, reason_if_fail)
        - created_slots: list[TeachingSlot] nếu xếp được >=1 slot
        - reason_if_fail: None nếu ok, hoặc chuỗi mô tả lý do nếu không xếp được.
    """
    semester: Semester = section.semester
    subject = section.subject

    # Môn thực tập thì bỏ (không xếp phòng, bạn xử lý riêng)
    from .services import periods_per_session_for_subject  # nếu helper ở cùng file thì bỏ import này

    per_session = periods_per_session_for_subject(section)
    if per_session == 0:
        return [], "Môn thực tập không xếp phòng trong TKB"

    # Lấy tất cả tuần hợp lệ (không nghỉ) từ start_week_index trở đi
    all_weeks = list(
        SemesterWeek.objects.filter(
            semester=semester,
            is_break=False,
            index__gte=start_week_index
        ).order_by("index")
    )
    if not all_weeks:
        return [], f"Không tìm thấy tuần nào từ tuần {start_week_index}"

    # Tổng tiết cho lớp học phần này
    total_periods = section.planned_periods or subject.total_periods

    # Số buổi cần thiết
    sessions_needed = ceil(total_periods / per_session)

    # Số tuần cần thiết nếu chưa truyền weeks_count
    if weeks_count is None:
        weeks_needed = ceil(sessions_needed / sessions_per_week)
    else:
        weeks_needed = weeks_count

    # Cắt danh sách tuần theo weeks_needed
    weeks_for_course = all_weeks[:weeks_needed]
    if not weeks_for_course:
        return [], "Không có đủ tuần để xếp (weeks_for_course rỗng)"

    # Chuẩn bị phòng
    from .services import get_candidate_rooms_for_section  # nếu helper ở cùng file thì bỏ import này

    rooms = get_candidate_rooms_for_section(section)
    if allowed_room_codes:
        rooms = [r for r in rooms if r.code in allowed_room_codes]

    if not rooms and subject.subject_type != "THUC_TAP":
        return [], "Không có phòng phù hợp (sau khi áp dụng allowed_room_codes)"

    # Sẽ tạo tối đa sessions_needed buổi
    created_slots = []

    # Helper conflict check
    from .services import (
        instructor_is_available,
        has_conflict_for_room,
        has_conflict_for_class,
        has_conflict_for_instructor,
    )

    # Giả sử ta muốn dạy đều các tuần, mỗi tuần 'sessions_per_week' buổi
    # => tổng buổi chúng ta cố gắng xếp = min(sessions_needed, sessions_per_week * len(weeks_for_course))
    max_sessions = min(sessions_needed, sessions_per_week * len(weeks_for_course))

    day_candidates = [1, 2, 3, 4, 5, 6]  # Th2..Th7
    start_period_candidates = [1, 6]     # sáng, chiều

    # Chiến lược đơn giản: lặp qua tuần, mỗi tuần cố gắng xếp từ 0 tới sessions_per_week buổi
    sessions_created = 0

    for week in weeks_for_course:
        if sessions_created >= max_sessions:
            break

        weekly_sessions = 0

        for day in day_candidates:
            if weekly_sessions >= sessions_per_week or sessions_created >= max_sessions:
                break

            for start_p in start_period_candidates:
                if weekly_sessions >= sessions_per_week or sessions_created >= max_sessions:
                    break

                end_p = start_p + per_session - 1

                # Check GV rảnh
                if not instructor_is_available(section.instructor, day, start_p, end_p):
                    continue

                # Thử từng phòng
                room_options = rooms if rooms else [None]

                for room in room_options:
                    # Check trùng phòng
                    if has_conflict_for_room(room, semester, day, start_p, end_p, [week]):
                        continue

                    # Check trùng lớp
                    if has_conflict_for_class(section.classes.all(), semester, day, start_p, end_p, [week]):
                        continue

                    # Check trùng GV
                    if has_conflict_for_instructor(section.instructor, semester, day, start_p, end_p, [week]):
                        continue

                    # OK -> tạo slot cho tuần này
                    slot = TeachingSlot.objects.create(
                        course_section=section,
                        room=room,
                        day_of_week=day,
                        start_period=start_p,
                        end_period=end_p,
                        method="",
                        is_locked=False,
                    )
                    slot.weeks.set([week])

                    created_slots.append(slot)
                    weekly_sessions += 1
                    sessions_created += 1

                    break  # xong 1 slot, sang tìm slot tiếp theo

    if not created_slots:
        return [], "Không tìm được slot phù hợp (phòng/lớp/GV đều bị trùng hoặc hạn chế)"

    return created_slots, None

def generate_semester_weeks(semester: Semester, total_weeks: int = 20):
    """
    Sinh các bản ghi SemesterWeek cho 1 Học kỳ:
    - Mặc định: 20 tuần liên tiếp kể từ semester.start_date
    - is_break = False hết, sau này bạn có thể set tuần nghỉ riêng nếu cần.

    Nếu đã có SemesterWeek rồi thì hàm sẽ bỏ qua (không tạo trùng index).
    """
    start = semester.start_date

    created = []

    for i in range(total_weeks):
        week_index = i + 1
        week_start = start + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)

        sw, is_created = SemesterWeek.objects.get_or_create(
            semester=semester,
            index=week_index,
            defaults={
                "start_date": week_start,
                "end_date": week_end,
                "is_break": False,
            },
        )
        if is_created:
            created.append(sw)

    return created

def auto_schedule_single_section_fixed(section: CourseSection):
    """
    Xếp TKB cho MỘT Lớp học phần theo kiểu:
      - 1 buổi/tuần
      - Cố định 1 (Thứ, Tiết, Phòng) cho tất cả các tuần
    Trả về: (slot, error_message)
      - slot: TeachingSlot nếu xếp được
      - error_message: None nếu ok, hoặc chuỗi nếu lỗi
    """

    semester = section.semester
    subject = section.subject

    # 1. Xác định số tiết / buổi
    per_session = periods_per_session_for_subject(section)
    if per_session <= 0:
        return None, "Môn này không xếp TKB (vd: THỰC TẬP)"

    # 2. Lấy danh sách tuần hợp lệ
    all_weeks = list(
        SemesterWeek.objects.filter(
            semester=semester,
            is_break=False
        ).order_by("index")
    )
    if not all_weeks:
        return None, "Học kỳ không có tuần học nào"

    start_week_index = section.start_week or all_weeks[0].index
    weeks_candidate = [w for w in all_weeks if w.index >= start_week_index]

    if section.week_count:
        weeks_candidate = weeks_candidate[: section.week_count]

    if not weeks_candidate:
        return None, "Không có tuần dạy hợp lệ sau khi áp dụng start_week / week_count"

    # 3. Tính số buổi cần dạy (sessions_needed)
    total_periods = section.planned_periods or subject.total_periods
    if not total_periods or total_periods <= 0:
        return None, "Không xác định được tổng số tiết cho lớp học phần"

    sessions_needed = ceil(total_periods / per_session)

    # 4. Mặc định 1 buổi/tuần -> cần 'sessions_needed' tuần
    weeks_for_course = weeks_candidate[:sessions_needed]
    if not weeks_for_course:
        return None, "Không đủ tuần để xếp đủ số buổi môn học"

    # 5. Lấy danh sách phòng phù hợp
    rooms = get_candidate_rooms_for_section(section)
    # Nếu là môn không cần phòng thì rooms có thể rỗng, ta cho phép None
    if not rooms and subject.subject_type != "THUC_TAP":
        # Không có phòng phù hợp -> thôi chịu
        return None, "Không tìm được phòng phù hợp"

    # 6. Thử tất cả combo (Thứ, Tiết, Phòng) xem combo nào dùng được cho TẤT CẢ tuần
    day_candidates = [1, 2, 3, 4, 5, 6]  # Thứ 2..7
    start_period_candidates = [1, 6]     # Sáng, chiều

    for day in day_candidates:
        for start_p in start_period_candidates:
            end_p = start_p + per_session - 1

            # GV có rảnh ở khung giờ này không?
            if not instructor_is_available(section.instructor, day, start_p, end_p):
                continue

            room_options = rooms if rooms else [None]

            for room in room_options:
                # Check trùng phòng / lớp / GV TRÊN TOÀN BỘ weeks_for_course
                if has_conflict_for_room(room, semester, day, start_p, end_p, weeks_for_course):
                    continue

                if has_conflict_for_class(section.classes.all(), semester, day, start_p, end_p, weeks_for_course):
                    continue

                if has_conflict_for_instructor(section.instructor, semester, day, start_p, end_p, weeks_for_course):
                    continue

                # OK -> tạo 1 slot duy nhất, gắn tất cả tuần
                slot = TeachingSlot.objects.create(
                    course_section=section,
                    room=room,
                    day_of_week=day,
                    start_period=start_p,
                    end_period=end_p,
                    method="",
                    is_locked=False,
                )
                slot.weeks.set(weeks_for_course)

                return slot, None

    # Nếu chạy hết mà chưa đặt được
    return None, "Không tìm được (Thứ/Tiết/Phòng) dùng chung cho tất cả các tuần"

def auto_schedule_whole_semester_fixed(semester: Semester, department_code: str = "CNTT", reset_existing: bool = True):
    """
    Xếp TKB cho TOÀN BỘ LHP của 1 Học kỳ (theo khoa):
      - Với mỗi CourseSection:
          + (tuỳ chọn) Xoá toàn bộ slot cũ nếu reset_existing=True
          + Gọi auto_schedule_single_section_fixed(section)
      - Ưu tiên: 1 buổi/tuần, cùng 1 Thứ/Tiết/Phòng/GV cho tất cả tuần.

    Trả về:
      (scheduled_sections, failed_sections)
      - scheduled_sections: list[CourseSection]
      - failed_sections: list[(CourseSection, reason)]
    """
    from .models import CourseSection, TeachingSlot

    sections = CourseSection.objects.filter(
        semester=semester,
        classes__department__code=department_code,
    ).distinct().select_related("subject", "instructor").prefetch_related("classes")

    scheduled = []
    failed = []

    for section in sections:
        if reset_existing:
            TeachingSlot.objects.filter(course_section=section).delete()

        slot, error = auto_schedule_single_section_fixed(section)

        if slot:
            scheduled.append(section)
        else:
            failed.append((section, error))

    return scheduled, failed

def calculate_instructor_workload(academic_year: AcademicYear):
    """
    Tính KHỐI LƯỢNG cho từng giảng viên trong 1 Năm học.

    - ĐM GIẢNG DẠY gốc       = instructor.teaching_quota
    - ĐM HÀNH CHÍNH gốc      = instructor.admin_quota

    Mỗi nhiệm vụ (Trưởng khoa, GVCN, Tập sự...):
      - Có % giảm (teaching_reduction_percent, admin_reduction_percent)
      - Có số tháng (months)

    Giờ giảm cho MỖI nhiệm vụ:
      teaching_hours_reduced = teaching_quota_gốc * (percent/100) * (months / ACADEMIC_YEAR_MONTHS)
      admin_hours_reduced    = admin_quota_gốc    * (percent/100) * (months / ACADEMIC_YEAR_MONTHS)

    Sau đó:
      ĐM GD còn lại  = ĐM GD gốc  - tổng giờ giảm GD
      ĐM HC còn lại  = ĐM HC gốc  - tổng giờ giảm HC
    """

    results = []

    # LẤY TẤT CẢ GIẢNG VIÊN (KHÔNG FILTER GÌ HẾT)
    instructors = Instructor.objects.all().order_by("name")

    for ins in instructors:
        # ====== ĐỊNH MỨC GỐC ======
        base_teaching_quota = ins.teaching_quota or 0
        base_admin_quota = ins.admin_quota or 0

        # ====== NHIỆM VỤ GIẢM ĐỊNH MỨC ======
        duties_qs = InstructorDuty.objects.filter(
            instructor=ins,
            academic_year=academic_year,
        ).select_related("reduction_type")

        duties = list(duties_qs)
        duty_breakdown = []

        total_teaching_reduced_hours = 0.0
        total_admin_reduced_hours = 0.0

        for d in duties:
            months = d.months or 0
            factor = months / ACADEMIC_YEAR_MONTHS if ACADEMIC_YEAR_MONTHS > 0 else 1.0

            t_percent = d.reduction_type.teaching_reduction_percent or 0.0
            a_percent = d.reduction_type.admin_reduction_percent or 0.0

            teaching_hours_reduced = base_teaching_quota * (t_percent / 100.0) * factor
            admin_hours_reduced = base_admin_quota * (a_percent / 100.0) * factor

            total_teaching_reduced_hours += teaching_hours_reduced
            total_admin_reduced_hours += admin_hours_reduced

            duty_breakdown.append({
                "obj": d,
                "months": months,
                "teaching_percent": t_percent,
                "admin_percent": a_percent,
                "teaching_hours": teaching_hours_reduced,
                "admin_hours": admin_hours_reduced,
            })

        # Không cho ĐM bị âm
        teaching_quota_after = max(0.0, base_teaching_quota - total_teaching_reduced_hours)
        admin_quota_after = max(0.0, base_admin_quota - total_admin_reduced_hours)

        # ====== GIỜ DẠY (từ TKB) ======
        slots = TeachingSlot.objects.filter(
            course_section__semester__academic_year=academic_year,
            course_section__instructor=ins,
        ).prefetch_related("weeks")

        total_periods = 0
        for s in slots:
            num_weeks = s.weeks.count()
            periods_per_session = (s.end_period - s.start_period + 1)
            total_periods += periods_per_session * num_weeks

        teaching_hours = float(total_periods)  # 1 tiết = 1 giờ chuẩn (tạm)

        # Quy đổi dạy -> giờ hành chính
        teaching_to_admin_hours = teaching_hours * (ins.conversion_ratio or 0)

        # ====== NCKH: tính theo ResearchMember với tỷ lệ chia ======
        member_qs = ResearchMember.objects.filter(
            instructor=ins,
            project__year=academic_year,
        ).select_related("project").prefetch_related("project__members")

        rp_hours = 0.0

        for m in member_qs:
            project = m.project
            members = list(project.members.all().order_by("order", "id"))
            if not members:
                continue

            # Nếu đã nhập share_ratio > 0 -> dùng số đó
            if any(mm.share_ratio and mm.share_ratio > 0 for mm in members):
                total_ratio = sum((mm.share_ratio or 0) for mm in members)
                if total_ratio <= 0:
                    share = 1.0 / len(members)  # fallback chia đều
                else:
                    this_member = next(
                        (mm for mm in members if mm.instructor_id == ins.id),
                        None,
                    )
                    if this_member and this_member.share_ratio:
                        share = this_member.share_ratio / total_ratio
                    else:
                        share = 0.0
            else:
                # Chưa nhập share_ratio -> tự chia theo quy tắc 6:4, 4:3:3, 4:2:2:2...
                weights = suggest_share_weights(len(members))
                total_w = sum(weights) or 1.0
                share = 0.0
                for idx, mm in enumerate(members):
                    if mm.instructor_id == ins.id:
                        share = weights[idx] / total_w
                        break

            rp_hours += (project.hours or 0) * share

        # ====== TTDN / BỒI DƯỠNG ======
        ei_hours = EnterpriseInternship.objects.filter(
            instructor=ins, year=academic_year
        ).aggregate(models.Sum("hours"))["hours__sum"] or 0

        pd_hours = ProfessionalDevelopment.objects.filter(
            instructor=ins, year=academic_year
        ).aggregate(models.Sum("hours"))["hours__sum"] or 0

        other_admin_hours = rp_hours + ei_hours + pd_hours

        admin_hours_total = teaching_to_admin_hours + other_admin_hours

        # ====== DƯ / THIẾU so với ĐM ĐÃ TRỪ GIẢM ======
        teaching_overload = teaching_hours - teaching_quota_after
        admin_overload = admin_hours_total - admin_quota_after

        results.append({
            "instructor": ins,
            "duties": duties,
            "duty_breakdown": duty_breakdown,

            "base_teaching_quota": base_teaching_quota,
            "base_admin_quota": base_admin_quota,

            "teaching_reduced_hours": total_teaching_reduced_hours,
            "admin_reduced_hours": total_admin_reduced_hours,

            "teaching_quota_adj": teaching_quota_after,
            "admin_quota_adj": admin_quota_after,

            "teaching_hours": teaching_hours,
            "teaching_overload": teaching_overload,

            "admin_hours_total": admin_hours_total,
            "admin_overload": admin_overload,

            "rp_hours": rp_hours,
            "ei_hours": ei_hours,
            "pd_hours": pd_hours,
            "teaching_to_admin_hours": teaching_to_admin_hours,
        })

    return results