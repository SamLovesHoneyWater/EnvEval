// EnvEval Benchmark Website JavaScript

// Global variables
let benchmarkData = null;
let maxFcsScore = 0;

// Load benchmark data directly from dataset folder
async function loadBenchmarkData() {
  try {
    console.log("🔍 Loading benchmark data from dataset folder...");

    // First, get the list of result directories
    const resultDirs = await getResultDirectories();
    console.log("📁 Found result directories:", resultDirs);

    // Load data from each directory
    const results = [];
    for (const dir of resultDirs) {
      try {
        const resultData = await loadResultFromDirectory(dir);
        if (resultData) {
          results.push(resultData);
        }
      } catch (error) {
        console.warn(`⚠️ Failed to load data from ${dir}:`, error.message);
      }
    }

    // Create benchmark data structure
    benchmarkData = {
      metadata: {
        title: "EnvEval Benchmark Results",
        description:
          "Comprehensive evaluation results for environment configuration and code execution capabilities",
        last_updated: new Date().toISOString().split("T")[0],
        total_models: results.length,
        categories: [...new Set(results.map((r) => r.category))],
      },
      results: results,
    };

    // Find the best score
    maxFcsScore = Math.max(...benchmarkData.results.map((r) => r.fcs_score));

    // Mark the best result
    benchmarkData.results.forEach((result) => {
      result.is_best = result.fcs_score === maxFcsScore;
    });

    console.log("✅ Successfully loaded", results.length, "benchmark results");

    // Generate the results table
    generateResultsTable();

    // Initialize table interactions after data is loaded
    initializeTableInteractions();
  } catch (error) {
    console.error("❌ Error loading benchmark data:", error);
    showErrorMessage(
      `Failed to load benchmark data: ${error.message}. Please make sure the dataset/results folder is accessible.`
    );
  }
}

// Get list of result directories from the dataset folder
async function getResultDirectories() {
  const knownDirs = [
    "baseline-claude-code-haiku3.5",
    "baseline-claude-code-opus4",
    "baseline-codex-gpt4.1-mini",
    "baseline-codex-gpt4.1",
    "envgym-claude-haiku3.5",
    "envgym-claude-opus4",
    "envgym-deepseek-r1",
    "envgym-deepseek-v3",
    "envgym-gemini-2.5-pro",
    "envgym-gpt4.1-mini",
    "envgym-gpt4.1",
  ];

  // Filter to only include directories that actually have result.json
  const validDirs = [];
  for (const dir of knownDirs) {
    try {
      const response = await fetch(`../dataset/results/${dir}/result.json`);
      if (response.ok) {
        validDirs.push(dir);
      }
    } catch (error) {
      console.warn(`Directory ${dir} not accessible:`, error.message);
    }
  }

  return validDirs;
}

// Load result data from a specific directory
async function loadResultFromDirectory(dirName) {
  const basePath = `../dataset/results/${dirName}`;

  // Load result.json
  const resultResponse = await fetch(`${basePath}/result.json`);
  if (!resultResponse.ok) {
    throw new Error(`Failed to load result.json from ${dirName}`);
  }

  const resultData = await resultResponse.json();

  // Check if logo exists
  let hasLogo = false;
  try {
    const logoResponse = await fetch(`${basePath}/logo.png`);
    hasLogo = logoResponse.ok;
  } catch (error) {
    hasLogo = false;
  }

  // Determine category from directory name
  const category = dirName.startsWith("baseline-") ? "baseline" : "envgym";

  return {
    id: dirName,
    method: resultData.method,
    model: resultData.model,
    fcs_score: resultData.fcs_score,
    category: category,
    status: "completed",
    has_logo: hasLogo,
    has_detailed_data: true,
    logo: hasLogo ? `${basePath}/logo.png` : null,
    is_best: false, // Will be set later
  };
}

// Generate the results table from loaded data
function generateResultsTable() {
  const tbody = document.getElementById("results-tbody");
  if (!tbody || !benchmarkData) return;

  // Clear loading message
  tbody.innerHTML = "";

  // Sort results by FCS score (highest first)
  const sortedResults = [...benchmarkData.results].sort(
    (a, b) => b.fcs_score - a.fcs_score
  );

  // Generate table rows
  sortedResults.forEach((result, index) => {
    const row = document.createElement("tr");
    row.className = `result-row ${
      result.status !== "completed" ? "placeholder" : ""
    }`;

    // Method column with integrated logo
    const methodCell = document.createElement("td");
    methodCell.className = "method-cell";

    // Create logo image if available
    if (result.has_logo && result.logo) {
      const logoImg = document.createElement("img");
      logoImg.src = result.logo;
      logoImg.alt = `${result.method} logo`;
      logoImg.className = "method-logo";
      logoImg.onerror = function () {
        this.style.display = "none";
      };
      methodCell.appendChild(logoImg);
    }

    // Create method text
    const methodText = document.createElement("span");
    methodText.textContent = result.method;
    methodText.className = "method-text";

    methodCell.appendChild(methodText);
    row.appendChild(methodCell);

    // Model column
    const modelCell = document.createElement("td");
    modelCell.className = "model-cell";
    modelCell.textContent = result.model;
    row.appendChild(modelCell);

    // FCS Score column
    const scoreCell = document.createElement("td");
    scoreCell.className = `score-cell ${result.is_best ? "best-score" : ""}`;

    if (result.status !== "completed") {
      scoreCell.innerHTML = '<span class="placeholder-text">Coming Soon</span>';
    } else {
      scoreCell.innerHTML = `<span class="score-value">${result.fcs_score.toFixed(
        2
      )}%</span>`;

      // Add crown icon for best result
      if (result.is_best) {
        const crownIcon = document.createElement("i");
        crownIcon.className = "fas fa-crown crown-icon";
        scoreCell.appendChild(crownIcon);
      }
    }
    row.appendChild(scoreCell);

    tbody.appendChild(row);
  });
}

// Show error message
function showErrorMessage(message) {
  const tbody = document.getElementById("results-tbody");
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="3" class="error-message">
          <i class="fas fa-exclamation-triangle"></i>
          ${message}
        </td>
      </tr>
    `;
  }
}

document.addEventListener("DOMContentLoaded", function () {
  // Load data and initialize website
  loadBenchmarkData();
  initializeAnimations();
  initializeScrollEffects();
  initializeLinkHandlers();
});

// Initialize scroll-triggered animations
function initializeAnimations() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  };

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("animate-in");

        // Special handling for table rows
        if (entry.target.classList.contains("results-table")) {
          animateTableRows(entry.target);
        }

        // Special handling for insight cards
        if (entry.target.classList.contains("insights-grid")) {
          animateInsightCards(entry.target);
        }
      }
    });
  }, observerOptions);

  // Observe elements for animation
  const elementsToAnimate = document.querySelectorAll(
    ".intro-section, .results-section, .insights-section"
  );
  elementsToAnimate.forEach((el) => observer.observe(el));
}

// Animate table rows with staggered effect
function animateTableRows(table) {
  const rows = table.querySelectorAll("tbody tr");
  rows.forEach((row, index) => {
    setTimeout(() => {
      row.style.opacity = "1";
      row.style.transform = "translateY(0)";

      // Animate performance bars
      const bar = row.querySelector(".bar");
      if (bar) {
        const width = bar.style.width;
        bar.style.width = "0%";
        setTimeout(() => {
          bar.style.width = width;
        }, 100);
      }
    }, index * 100);
  });
}

// Animate insight cards
function animateInsightCards(grid) {
  const cards = grid.querySelectorAll(".insight-card");
  cards.forEach((card, index) => {
    setTimeout(() => {
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    }, index * 200);
  });
}

// Initialize table interactions
function initializeTableInteractions() {
  const table = document.querySelector(".results-table");
  if (!table) return;

  // Add hover effects to rows
  const rows = table.querySelectorAll("tbody tr");
  rows.forEach((row) => {
    row.addEventListener("mouseenter", function () {
      // Highlight the row
      this.style.backgroundColor = "#f0f9ff";

      // Pulse the performance bar
      const bar = this.querySelector(".bar");
      if (bar) {
        bar.style.transform = "scaleX(1.02)";
        bar.style.filter = "brightness(1.1)";
      }
    });

    row.addEventListener("mouseleave", function () {
      // Reset row styling
      this.style.backgroundColor = "";

      // Reset performance bar
      const bar = this.querySelector(".bar");
      if (bar) {
        bar.style.transform = "scaleX(1)";
        bar.style.filter = "brightness(1)";
      }
    });
  });

  // Add click to highlight functionality
  rows.forEach((row) => {
    row.addEventListener("click", function () {
      // Remove previous highlights
      rows.forEach((r) => r.classList.remove("highlighted"));

      // Add highlight to clicked row
      this.classList.add("highlighted");

      // Show detailed information (placeholder for future enhancement)
      showModelDetails(this);
    });
  });
}

// Show model details (enhanced function)
function showModelDetails(row) {
  const modelCell =
    row.querySelector("td:nth-child(3)") ||
    row.querySelector("td:nth-child(2)");
  const model = modelCell ? modelCell.textContent : "Unknown Model";
  const score = row.querySelector(".score").textContent;

  // Try to find detailed data for this model
  let detailedInfo = null;
  if (benchmarkData) {
    detailedInfo = benchmarkData.results.find(
      (r) => r.model === model || r.model.includes(model)
    );
  }

  // Create a temporary notification
  const notification = document.createElement("div");
  notification.className = "model-notification";

  let notificationContent = `
    <div class="notification-content">
      <strong>${model}</strong><br>
      FCS Score: ${score}
  `;

  // Add additional info if available
  if (detailedInfo) {
    notificationContent += `<br>
      Method: ${detailedInfo.agent}<br>
      Category: ${detailedInfo.category}<br>
      Status: ${detailedInfo.status}
    `;

    if (detailedInfo.has_detailed_data) {
      notificationContent += `<br><small>📊 Detailed data available</small>`;
    }

    if (detailedInfo.is_best) {
      notificationContent += `<br><small>🏆 Best performing model</small>`;
    }
  }

  notificationContent += `
      <button class="close-notification">&times;</button>
    </div>
  `;

  notification.innerHTML = notificationContent;

  document.body.appendChild(notification);

  // Auto remove after 3 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.remove();
    }
  }, 3000);

  // Add close button functionality
  notification
    .querySelector(".close-notification")
    .addEventListener("click", () => {
      notification.remove();
    });
}

// Initialize scroll effects
function initializeScrollEffects() {
  let ticking = false;

  function updateScrollEffects() {
    const scrollY = window.pageYOffset;
    const header = document.querySelector(".header");

    // Add/remove header shadow based on scroll
    if (scrollY > 10) {
      header.classList.add("scrolled");
    } else {
      header.classList.remove("scrolled");
    }

    // Parallax effect for background
    const main = document.querySelector(".main");
    if (main) {
      main.style.transform = `translateY(${scrollY * 0.1}px)`;
    }

    ticking = false;
  }

  function requestScrollUpdate() {
    if (!ticking) {
      requestAnimationFrame(updateScrollEffects);
      ticking = true;
    }
  }

  window.addEventListener("scroll", requestScrollUpdate);
}

// Initialize link handlers
function initializeLinkHandlers() {
  // Handle external link clicks with animations
  const linkButtons = document.querySelectorAll(".link-btn");

  linkButtons.forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();

      // Add click animation
      this.style.transform = "scale(0.95)";
      setTimeout(() => {
        this.style.transform = "";
      }, 150);

      // Show coming soon message or redirect
      const linkType = this.querySelector("span").textContent;
      showComingSoonMessage(linkType);
    });

    // Add ripple effect on click
    button.addEventListener("click", function (e) {
      const ripple = document.createElement("span");
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;

      ripple.style.width = ripple.style.height = size + "px";
      ripple.style.left = x + "px";
      ripple.style.top = y + "px";
      ripple.classList.add("ripple");

      this.appendChild(ripple);

      setTimeout(() => {
        ripple.remove();
      }, 600);
    });
  });
}

// Show coming soon message
function showComingSoonMessage(linkType) {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Coming Soon</h3>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-body">
                <p>The ${linkType} link will be available soon. Stay tuned for updates!</p>
                <div class="modal-icon">
                    <i class="fas fa-rocket"></i>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn">Got it</button>
            </div>
        </div>
    `;

  document.body.appendChild(modal);

  // Add event listeners for closing modal
  const closeButtons = modal.querySelectorAll(".modal-close, .modal-btn");
  closeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      modal.remove();
    });
  });

  // Close on overlay click
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.remove();
    }
  });

  // Auto close after 5 seconds
  setTimeout(() => {
    if (modal.parentNode) {
      modal.remove();
    }
  }, 5000);
}

// Add CSS for dynamic elements
const dynamicStyles = `
<style>
.animate-in {
    animation: slideInUp 0.6s ease-out forwards;
}

@keyframes slideInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.results-table tbody tr {
    opacity: 0;
    transform: translateY(20px);
    transition: all 0.3s ease;
}

.insight-card {
    opacity: 0;
    transform: translateY(30px);
    transition: all 0.4s ease;
}

.highlighted {
    background-color: #fef3c7 !important;
    border-left: 4px solid #f59e0b !important;
}

.header.scrolled {
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15) !important;
}

.ripple {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    transform: scale(0);
    animation: rippleEffect 0.6s linear;
    pointer-events: none;
}

@keyframes rippleEffect {
    to {
        transform: scale(2);
        opacity: 0;
    }
}

.model-notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    padding: 1rem;
    z-index: 1000;
    animation: slideInRight 0.3s ease-out;
    border-left: 4px solid #667eea;
}

.notification-content {
    position: relative;
    padding-right: 30px;
}

.close-notification {
    position: absolute;
    top: -5px;
    right: -10px;
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #64748b;
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    animation: fadeIn 0.3s ease-out;
}

.modal-content {
    background: white;
    border-radius: 16px;
    max-width: 400px;
    width: 90%;
    animation: scaleIn 0.3s ease-out;
    overflow: hidden;
}

.modal-header {
    padding: 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.modal-header h3 {
    margin: 0;
    font-size: 1.25rem;
}

.modal-close {
    background: none;
    border: none;
    color: white;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: background-color 0.2s;
}

.modal-close:hover {
    background-color: rgba(255, 255, 255, 0.2);
}

.modal-body {
    padding: 2rem;
    text-align: center;
}

.modal-body p {
    margin-bottom: 1.5rem;
    color: #64748b;
    line-height: 1.6;
}

.modal-icon {
    font-size: 3rem;
    color: #667eea;
    margin-bottom: 1rem;
}

.modal-footer {
    padding: 1rem 2rem 2rem;
    text-align: center;
}

.modal-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 0.75rem 2rem;
    border-radius: 25px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
}

.modal-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes scaleIn {
    from {
        transform: scale(0.9);
        opacity: 0;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}
</style>
`;

// Inject dynamic styles
document.head.insertAdjacentHTML("beforeend", dynamicStyles);
