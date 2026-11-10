const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector(".site-nav");

menuButton?.addEventListener("click", () => {
  const isOpen = menuButton.getAttribute("aria-expanded") === "true";
  menuButton.setAttribute("aria-expanded", String(!isOpen));
  menuButton.setAttribute("aria-label", isOpen ? "Ouvrir le menu" : "Fermer le menu");
  navigation?.classList.toggle("is-open", !isOpen);
});

navigation?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    menuButton?.setAttribute("aria-expanded", "false");
    menuButton?.setAttribute("aria-label", "Ouvrir le menu");
    navigation.classList.remove("is-open");
  });
});

const configuredInstallerUrl = document.documentElement.dataset.installerUrl?.trim();
const isGitHubPages = location.hostname.endsWith(".github.io");
const pagesProject = isGitHubPages
  ? location.pathname.split("/").filter(Boolean)[0]
  : "";
const pagesOwner = isGitHubPages
  ? location.hostname.slice(0, -".github.io".length)
  : "";
const releaseRepository = pagesProject || (pagesOwner ? `${pagesOwner}.github.io` : "");
const installerUrl = configuredInstallerUrl || (pagesOwner && releaseRepository
  ? `https://github.com/${pagesOwner}/${releaseRepository}/releases/latest/download/DebloatCraft.exe`
  : "");
const downloadState = document.querySelector("#download-state");

document.querySelectorAll("[data-installer]").forEach((link) => {
  if (!installerUrl) return;
  link.href = installerUrl;
  link.removeAttribute("aria-disabled");
  link.removeAttribute("tabindex");
  if (downloadState) downloadState.textContent = "Téléchargement direct, gratuit. Windows demandera ton autorisation avant l'application.";
});

if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.documentElement.classList.add("reveal-ready");
  const revealTargets = document.querySelectorAll(".section-heading, .settings-list li, .caution-row, .install-step, .faq-list details");
  revealTargets.forEach((element) => element.classList.add("reveal"));
  const observer = new IntersectionObserver((entries, currentObserver) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      currentObserver.unobserve(entry.target);
    });
  }, { threshold: 0.12 });
  revealTargets.forEach((element) => observer.observe(element));
}