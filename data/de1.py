
def tongchan(N):
    tong = 0
    for i in range(N):
        tong += i
    return tong

def is_prime(N):
    for i in range(2,N):
        if N%i== 0:
            return False
    return True
print(tongchan(8))
if(is_prime(8)):
    print("La nguyen to!")
else:
    print("Ko la nguyen to!")
    
def xu_ly_van_ban(s):
    # 1. Đếm số lượng chữ số
    dem_so = 0
    for ky_tu in s:
        if ky_tu.isdigit(): # Hàm kiểm tra xem ký tự có phải là số không
            dem_so += 1
            
    # 2. Tìm từ dài nhất
    danh_sach_tu = s.split() # Tách chuỗi thành danh sách các từ dựa vào khoảng trắng
    
    tu_dai_nhat = ""
    
    if len(danh_sach_tu) > 0:
        tu_dai_nhat = danh_sach_tu[0] # Giả sử từ đầu tiên là dài nhất
        for tu in danh_sach_tu:
            # Chỉ cập nhật nếu tìm thấy từ dài hơn hẳn
            # (Dùng dấu > sẽ giữ lại từ xuất hiện trước nếu độ dài bằng nhau)
            if len(tu) > len(tu_dai_nhat):
                tu_dai_nhat = tu
    
    # In kết quả ra màn hình (hoặc trả về tùy yêu cầu đề bài)
    print(f"Chuỗi ban đầu: {s}")
    print(f"- Số lượng ký tự số: {dem_so}")
    print(f"- Từ dài nhất: {tu_dai_nhat}")
    
    return dem_so, tu_dai_nhat

# --- Chạy thử nghiệm ---
s_input = "Python 2024 la ngon ngu lap trinh"
xu_ly_van_ban(s_input)
