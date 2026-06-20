// StayNova — small progressive-enhancement script (no frameworks)
document.addEventListener("DOMContentLoaded", () => {
  // Mobile nav toggle
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
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
});
