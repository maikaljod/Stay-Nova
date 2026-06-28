// StayNova — small progressive-enhancement script (no frameworks)
document.addEventListener("DOMContentLoaded", () => {
  // Mobile nav toggle
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
  }

  // Dark mode toggle
  const themeToggle = document.querySelector("#theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      if (isDark) {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("theme", "light");
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
        localStorage.setItem("theme", "dark");
      }
    });
  }

  // Auto-dismiss flash messages
  document.querySelectorAll(".flash").forEach((flash) => {
    const closeBtn = flash.querySelector("button");
    if (closeBtn) closeBtn.addEventListener("click", () => flash.remove());
    setTimeout(() => flash.remove(), 6000);
  });

  // Prevent selecting a check-out date before check-in
  const checkIn = document.querySelector("#check_in");
  const checkOut = document.querySelector("#check_out");
  if (checkIn && checkOut) {
    const sync = () => {
      if (checkIn.value) {
        const nextDay = new Date(checkIn.value);
        nextDay.setDate(nextDay.getDate() + 1);
        checkOut.min = nextDay.toISOString().split("T")[0];
        if (checkOut.value && checkOut.value <= checkIn.value) {
          checkOut.value = checkOut.min;
        }
      }
    };
    checkIn.addEventListener("change", sync);
    sync();
  }

  // Simple client-side password match hint (server still validates)
  const pw = document.querySelector("#password");
  const confirmPw = document.querySelector("#confirm_password");
  if (pw && confirmPw) {
    const check = () => {
      confirmPw.setCustomValidity(
        confirmPw.value && confirmPw.value !== pw.value ? "Passwords do not match" : ""
      );
    };
    pw.addEventListener("input", check);
    confirmPw.addEventListener("input", check);
  }

  // Confirm before destructive actions
  document.querySelectorAll("[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // Scroll-reveal: fade/slide elements in as they enter the viewport
  const revealTargets = document.querySelectorAll(".scroll-reveal");
  if (revealTargets.length) {
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("in-view");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      revealTargets.forEach((el) => observer.observe(el));
    } else {
      // No IntersectionObserver support: just show everything immediately
      revealTargets.forEach((el) => el.classList.add("in-view"));
    }
  }

  // Flip cards: hover already flips on desktop; tap-to-flip for touch devices
  document.querySelectorAll(".flip-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (!window.matchMedia("(hover: none)").matches) return; // desktop: let :hover handle it
      if (card.classList.contains("is-flipped")) return; // already flipped, allow the link through
      e.preventDefault();
      document.querySelectorAll(".flip-card.is-flipped").forEach((other) => {
        if (other !== card) other.classList.remove("is-flipped");
      });
      card.classList.add("is-flipped");
    });
  });
});
