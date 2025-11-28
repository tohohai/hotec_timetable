from django import forms
from .models import Semester, Room, StudentClass, Instructor, AcademicYear



class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Chọn file Excel (.xlsx)")
    

class SemesterChoiceForm(forms.Form):
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        label="Học kỳ",
    )
    department_code = forms.CharField(
        max_length=20,
        initial="CNTT",
        label="Mã Khoa",
        help_text="VD: CNTT",
    )


class SemiAutoScheduleForm(forms.Form):
    start_week_index = forms.IntegerField(
        min_value=1,
        label="Bắt đầu từ Tuần",
        help_text="VD: 1, 5, 10...",
    )
    sessions_per_week = forms.IntegerField(
        min_value=1,
        max_value=7,
        initial=2,
        label="Số buổi/tuần",
    )
    weeks_count = forms.IntegerField(
        required=False,
        min_value=1,
        label="Số tuần dạy (nếu bỏ trống sẽ tự tính)",
    )
    allowed_rooms = forms.ModelMultipleChoiceField(
        queryset=Room.objects.all(),
        required=False,
        label="Chỉ dùng các phòng (nếu không chọn sẽ dùng tất cả phòng phù hợp)",
        widget=forms.CheckboxSelectMultiple,
    )

# ==== FORM MỚI (CHỈ THÊM THÊM, KHÔNG ĐỤNG VÀO CÁI TRÊN) ====

class ClassTimetableForm(forms.Form):
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        label="Học kỳ",
    )
    student_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.all(),
        label="Lớp sinh viên",
    )


class InstructorTimetableForm(forms.Form):
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        label="Học kỳ",
    )
    instructor = forms.ModelChoiceField(
        queryset=Instructor.objects.all(),
        label="Giảng viên",
    )

class RoomTimetableForm(forms.Form):
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        label="Học kỳ",
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.all(),
        label="Phòng học",
    )

class InstructorWorkloadForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        label="Năm học",
    )
