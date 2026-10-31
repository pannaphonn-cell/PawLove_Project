/**
 * PawLove JavaScript Functions
 * ระบบสไลด์เลื่อนข่าวสารและกิจกรรมล่าสุดอัตโนมัติ (Animated News & Activities Carousel)
 */

// ข้อมูลข่าวสารและกิจกรรมล่าสุด (โหลดไดนามิกจากฐานข้อมูล)
let latestNewsList = [];

function loadLatestNewsData() {
  const dataElem = document.getElementById('latestNewsData');
  if (dataElem) {
    try {
      const rawData = JSON.parse(dataElem.textContent);
      if (Array.isArray(rawData) && rawData.length > 0) {
        latestNewsList = rawData.map(item => ({
          id: item.id,
          title: item.title,
          category: item.category || 'ข่าวประชาสัมพันธ์',
          summary: item.summary || item.content || '',
          image: item.image_url || '/static/uploads/pets/💛💛.jpg',
          author: item.author || 'แอดมิน PawLove',
          date: item.created_at ? item.created_at.slice(0, 10) : 'ล่าสุด'
        }));
      }
    } catch (e) {
      console.warn("Could not parse latestNewsData, using fallback.", e);
    }
  }

  // หากไม่มีข้อมูลจากฐานข้อมูล ให้ใช้ค่าสำรองที่เป็นข่าวสารและกิจกรรม
  if (!latestNewsList || latestNewsList.length === 0) {
    latestNewsList = [
      {
        id: 1,
        title: "อัปเดตอาการน้องมะลิ หลังเข้ารับการผ่าตัดช่วยเหลือสำเร็จ",
        category: "ข่าวการรักษา",
        summary: "น้องมะลิได้รับการผ่าตัดรักษาแผลเรียบร้อยแล้ว อาการปลอดภัยและอยู่ระหว่างพักฟื้น",
        author: "ทีมแพทย์สัตวแพทย์ PawLove",
        date: "ล่าสุด",
        image: "static/uploads/pets/💛💛.jpg"
      },
      {
        id: 2,
        title: "ขอบคุณทุกธารน้ำใจบริจาคค่ารักษาพยาบาลสัตว์จรจัด PawLove",
        category: "ระดมทุน & ช่วยเหลือ",
        summary: "ยอดบริจาคช่วยเหลือน้องๆ ทุกบาทถูกนำไปใช้เพื่อค่ายา ค่าเวชภัณฑ์ และการรักษาอย่างโปร่งใส",
        author: "มูลนิธิ PawLove",
        date: "ล่าสุด",
        image: "static/uploads/pets/catnew2.jpg"
      },
      {
        id: 3,
        title: "ประกาศหาบ้านใหม่ที่อบอุ่นให้น้องมอมแมม พร้อมเอกสารสุขภาพ",
        category: "หาบ้านใหม่",
        summary: "น้องนิสัยน่ารัก เข้ากับคนง่าย ฉีดวัคซีนและทำหมันครบถ้วน พร้อมย้ายสู่ครอบครัวใหม่",
        author: "โครงการหาบ้าน PawLove",
        date: "ล่าสุด",
        image: "static/uploads/pets/dognew3.jpg"
      }
    ];
  }
}

let currentNewsIndex = 0;
let newsSlideInterval = null;

// เปลี่ยนข่าวสารและกิจกรรมในสไลด์ (Auto Slide Smooth Transition & Divided Thumbnails)
function showNewsSlide(index) {
  if (!latestNewsList || latestNewsList.length === 0) return;
  currentNewsIndex = (index + latestNewsList.length) % latestNewsList.length;

  const titleElem = document.getElementById('animatedNewsTitle');
  const summaryElem = document.getElementById('animatedNewsSummary');
  const authorElem = document.getElementById('animatedNewsAuthor');
  const dateElem = document.getElementById('animatedNewsDate');
  const badgeElem = document.getElementById('newsSlideBadge');
  const imgElem = document.getElementById('animatedNewsImg');
  const counterElem = document.getElementById('newsSlideCounter');
  const totalElem = document.getElementById('newsSlideTotal');
  const timerBar = document.getElementById('newsTimerBar');

  if (titleElem && imgElem) {
    titleElem.style.opacity = '0';
    titleElem.style.transform = 'translateY(6px)';
    if (summaryElem) summaryElem.style.opacity = '0';
    imgElem.style.opacity = '0.2';
    imgElem.style.transform = 'scale(0.98)';

    setTimeout(() => {
      const data = latestNewsList[currentNewsIndex];
      titleElem.textContent = data.title;
      if (summaryElem) summaryElem.textContent = data.summary;
      if (authorElem) authorElem.textContent = `โดย ${data.author}`;
      if (dateElem) dateElem.innerHTML = `<i class="fa-regular fa-calendar-days" style="margin-right: 0.25rem;"></i>${data.date}`;
      if (badgeElem) badgeElem.innerHTML = `<i class="fa-solid fa-tag"></i> ${data.category}`;
      imgElem.src = data.image;

      if (counterElem) counterElem.textContent = currentNewsIndex + 1;
      if (totalElem) totalElem.textContent = latestNewsList.length;

      titleElem.style.opacity = '1';
      titleElem.style.transform = 'translateY(0)';
      if (summaryElem) summaryElem.style.opacity = '1';
      imgElem.style.opacity = '1';
      imgElem.style.transform = 'scale(1)';
    }, 240);
  }

  // อัปเดตไฮไลต์ของรายการข่าวฝั่งขวา (News List Items - Frosted Translucent Styling)
  const listItems = document.querySelectorAll('.news-list-item');
  listItems.forEach((item, i) => {
    const titleEl = item.querySelector('.news-item-title');
    if (i === currentNewsIndex) {
      item.classList.add('active-item');
      item.style.background = 'rgba(255, 247, 237, 0.95)';
      item.style.borderColor = 'rgba(249, 115, 22, 0.35)';
      item.style.transform = 'translateX(4px)';
      if (titleEl) titleEl.style.color = '#ea580c';
    } else {
      item.classList.remove('active-item');
      item.style.background = 'rgba(255, 255, 255, 0.4)';
      item.style.borderColor = 'transparent';
      item.style.transform = 'translateX(0)';
      if (titleEl) titleEl.style.color = '#1e293b';
    }
  });

  // อัปเดตจุด Indicators แบบแคปซูลโปร่งแสง
  const dots = document.querySelectorAll('.news-dot');
  dots.forEach((dot, i) => {
    if (i === currentNewsIndex) {
      dot.style.width = '28px';
      dot.style.background = '#f97316';
    } else {
      dot.style.width = '9px';
      dot.style.background = 'rgba(255, 255, 255, 0.35)';
    }
  });

  // รีเซ็ตหลอดเวลาวิ่ง 4 วินาที
  if (timerBar) {
    timerBar.style.transition = 'none';
    timerBar.style.width = '0%';
    setTimeout(() => {
      timerBar.style.transition = 'width 3900ms linear';
      timerBar.style.width = '100%';
    }, 50);
  }
}

function nextNews() {
  showNewsSlide(currentNewsIndex + 1);
  resetNewsTimer();
}

function prevNews() {
  showNewsSlide(currentNewsIndex - 1);
  resetNewsTimer();
}

function resetNewsTimer() {
  if (newsSlideInterval) clearInterval(newsSlideInterval);
  newsSlideInterval = setInterval(() => {
    showNewsSlide(currentNewsIndex + 1);
  }, 4000);
}

// เริ่มต้นเล่น Slider ข่าวสารอัตโนมัติ (เลื่อนเองอย่างต่อเนื่อง)
function initNewsSlider() {
  const newsContainer = document.getElementById('animatedNewsBanner');
  if (newsContainer) {
    loadLatestNewsData();
    showNewsSlide(0);
    resetNewsTimer();
  }
}

// ยอมรับข้อตกลงก่อนกรอกข้อมูลสัตว์
function acceptTermsAndProceed() {
  const checkbox = document.getElementById('terms_confirmed');
  if (checkbox) checkbox.checked = true;
  const formSection = document.getElementById('petFormSection');
  if (formSection) formSection.style.display = 'block';
  const termsPrompt = document.getElementById('termsPromptCard');
  if (termsPrompt) termsPrompt.style.display = 'none';
}

// เริ่มต้นการทำงานเมื่อโหลดหน้าเสร็จสมบูรณ์
document.addEventListener('DOMContentLoaded', function () {
  initNewsSlider();

  const passwordInput = document.getElementById('reg_password');
  if (passwordInput) {
    passwordInput.addEventListener('input', function () {
      const val = passwordInput.value;
      const upperCheck = /[A-Z]/.test(val);
      const lowerCheck = /[a-z]/.test(val);
      const numberCheck = /\d/.test(val);
      const lengthCheck = val.length >= 6;

      const upperElem = document.getElementById('rule_upper');
      const lowerElem = document.getElementById('rule_lower');
      const numberElem = document.getElementById('rule_number');
      const lengthElem = document.getElementById('rule_length');

      if (upperElem) upperElem.style.color = upperCheck ? '#10b981' : '#ef4444';
      if (lowerElem) lowerElem.style.color = lowerCheck ? '#10b981' : '#ef4444';
      if (numberElem) numberElem.style.color = numberCheck ? '#10b981' : '#ef4444';
      if (lengthElem) lengthElem.style.color = lengthCheck ? '#10b981' : '#ef4444';
    });
  }
});

// ฟังก์ชันพรีวิวรูปภาพสัตว์เมื่อเลือกไฟล์ผ่าน Choose File
function previewPetImage(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = function (e) {
      const previewImg = document.getElementById('imagePreview');
      const previewContainer = document.getElementById('imagePreviewContainer');
      const fileNameDisplay = document.getElementById('selectedFileName');
      if (previewImg) {
        previewImg.src = e.target.result;
      }
      if (previewContainer) {
        previewContainer.style.display = 'block';
      }
      if (fileNameDisplay) {
        fileNameDisplay.textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
      }
    };
    reader.readAsDataURL(file);
  }
}

