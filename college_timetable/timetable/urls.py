from django.urls import path
from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.home, name="home"),

    path("semester/", views.semester_overview, name="semester_overview"),
    path("sections/", views.section_list, name="section_list"),

    # ✅ TKB theo Lớp / Phòng / Giảng viên
    path("timetable/class/", views.timetable_by_class, name="timetable_by_class"),
    path("timetable/room/", views.timetable_by_room, name="timetable_by_room"),
    path("timetable/instructor/", views.timetable_by_instructor, name="timetable_by_instructor"),

    path("section/<int:pk>/schedule/", views.section_schedule, name="section_schedule"),

    path("instructor-workload/", views.instructor_workload_view, name="instructor_workload"),
    path(
        "instructor-workload/<int:instructor_id>/<int:year_id>/",
        views.instructor_workload_detail,
        name="instructor_workload_detail",
    ),

    path("import/", views.data_import_menu, name="data_import_menu"),
    path("import/<str:data_type>/", views.data_import_view, name="data_import_view"),
]
