let currentPage = 1;
let currentQuery = "";
let isSummaryLoading = false; // Global flag to track loading state

// Fetch and render default videos on page load
document.addEventListener("DOMContentLoaded", (event) => {
  fetch("/videos")
    .then((response) => response.json())
    .then((videos) => {
      displayVideos(videos);
      totalPages = videos.total_pages;
      document.getElementById(
        "pageCounter"
      ).innerText = `Page ${currentPage} of ${totalPages}`;
      updateButtons();
    });
});

function displayVideos(videos) {
  const container = document.getElementById("video-container");
  container.innerHTML = ""; // Clear previous results

  videos.data.forEach((video, index) => {
    console.log("Video data:", video); // Log video data to check structure

    const videoDiv = document.createElement("div");
    videoDiv.classList.add("video-card");
    videoDiv.setAttribute("data-video-id", video.video_id);
    videoDiv.setAttribute("data-card-id", `card-${index}`);
    videoDiv.setAttribute("data-video-title", video.title);
    videoDiv.style.cursor = "pointer"; // Make entire card clickable

    // Thumbnail
    const thumbnail = document.createElement("img");
    thumbnail.src = video.thumbnail;
    thumbnail.alt = video.title;

    videoDiv.appendChild(thumbnail);

    // Add video info div with proper class name
    const videoInfo = document.createElement("div");
    videoInfo.className = "video-info";

    const title = document.createElement("div");
    title.className = "video-title";
    title.textContent = video.title;
    videoInfo.appendChild(title);

    const details = document.createElement("div");
    details.className = "video-description";
    // Format the details string with views
    details.textContent = `${video.channel} • ${formatViews(
      video.views || 0
    )} views • ${formatPostDate(video.postDate)}`;
    videoInfo.appendChild(details);

    videoDiv.appendChild(videoInfo);

    // Add click handler to the entire card
    videoDiv.onclick = () => {
      console.log("Card clicked:", video.video_id); // Debug log
      fetchSummary(
        video.video_id,
        video.title,
        video.channel,
        video.views || 0,
        video.postDate
      );
    };

    container.appendChild(videoDiv);
  });
}

function formatViews(views) {
  if (views >= 1000000) {
    return (views / 1000000).toFixed(1) + "M";
  } else if (views >= 1000) {
    return (views / 1000).toFixed(0) + "K";
  } else {
    return views;
  }
}

function formatPostDate(postDate) {
  const postedDate = new Date(postDate);
  const currentDate = new Date();
  const timeDifference = currentDate - postedDate;

  const seconds = Math.floor(timeDifference / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  if (seconds < 60) {
    return `${seconds} second${seconds !== 1 ? "s" : ""} ago`;
  } else if (minutes < 60) {
    return `${minutes} minute${minutes !== 1 ? "s" : ""} ago`;
  } else if (hours < 24) {
    return `${hours} hour${hours !== 1 ? "s" : ""} ago`;
  } else if (days < 30) {
    return `${days} day${days !== 1 ? "s" : ""} ago`;
  } else if (days < 365) {
    return `${months} month${months !== 1 ? "s" : ""} ago`;
  } else {
    return `${years} year${years !== 1 ? "s" : ""} ago`;
  }
}

function updateButtons() {
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");

  if (currentPage === 1) {
    prevBtn.style.display = "none";
  } else {
    prevBtn.style.display = "inline-block";
  }

  if (currentPage === totalPages) {
    nextBtn.style.display = "none";
  } else {
    nextBtn.style.display = "inline-block";
  }
}

function nextPage() {
  if (currentPage < totalPages) {
    currentPage++;
    const encodedQuery = encodeURIComponent(currentQuery);

    fetch(`/next?query=${encodedQuery}`) // No pageToken in URL
      .then((response) => response.json())
      .then((videos) => {
        displayVideos(videos);
        totalPages = videos.total_pages;
        document.getElementById(
          "pageCounter"
        ).innerText = `Page ${currentPage} of ${totalPages}`;
        updateButtons();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
  }
}

function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    const encodedQuery = encodeURIComponent(currentQuery);

    fetch(`/prev?query=${encodedQuery}`) // No pageToken in URL
      .then((response) => response.json())
      .then((videos) => {
        displayVideos(videos);
        totalPages = videos.total_pages;
        document.getElementById(
          "pageCounter"
        ).innerText = `Page ${currentPage} of ${totalPages}`;
        updateButtons();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
  }
}

function searchVideos() {
  currentPage = 1;
  currentQuery = document.getElementById("search-query").value;

  // Regular expression to check if the query is a YouTube URL and extract video ID
  const youtubeRegex =
    /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/(watch\?v=)?(?<videoId>[a-zA-Z0-9_-]{11})/;
  const match = currentQuery.match(youtubeRegex);

  if (match && match.groups && match.groups.videoId) {
    // It's a YouTube URL, extract the video ID
    const videoId = match.groups.videoId;

    // Fetch and display the summary for this video
    fetchURLSummary(videoId, "YouTube Video Summary");

    return; // Exit the function as we've handled the YouTube URL case
  }

  // FIXED: Properly encode the query for URL
  const encodedQuery = encodeURIComponent(currentQuery);

  fetch(`/search?query=${encodedQuery}`)
    .then((response) => response.json())
    .then((videos) => {
      displayVideos(videos);
      document.getElementById(
        "pageCounter"
      ).innerText = `Page ${currentPage} of ${totalPages}`;
      updateButtons();

      // Scroll to the top of the page
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    })
    .catch((error) => console.error("Error fetching videos:", error));
}

function fetchURLSummary(videoId, videoTitle) {
  if (isSummaryLoading) {
    console.log("A summary is already loading. Please wait.");
    return;
  }

  isSummaryLoading = true; // Set loading flag

  // Hide all video cards
  const videoCards = document.querySelectorAll(".video-card");
  videoCards.forEach((card) => {
    card.style.display = "none";
  });

  // Show the loading overlay
  showLoadingOverlay();

  // Reference the main content area
  const mainContent = document.getElementById("video-container");
  if (!mainContent) {
    console.error("Main content area not found.");
    isSummaryLoading = false; // Reset flag
    hideLoadingOverlay(); // Ensure overlay is hidden
    return;
  }

  // Create and show the spinner in the main content area
  const spinnerContainer = document.createElement("div");
  spinnerContainer.className = "spinner-container";
  spinnerContainer.style.display = "flex";
  spinnerContainer.style.justifyContent = "center";
  spinnerContainer.style.alignItems = "center";
  spinnerContainer.style.height = "100vh"; // Full viewport height

  const spinner = document.createElement("div");
  spinner.className = "spinner";
  spinnerContainer.appendChild(spinner);

  // Save original content
  const originalContent = mainContent.innerHTML;

  // Replace content with spinner
  mainContent.innerHTML = "";
  mainContent.appendChild(spinnerContainer);

  // Fetch summary
  fetch(`/summarize?videoId=${videoId}`)
    .then((response) => response.json())
    .then((data) => {
      if (!data || typeof data.summary === "undefined") {
        console.error("Summary data is missing or undefined.");
        alert("The server did not return valid summary data.");
        return;
      }

      // Proceed with rendering summary
      const summary = data.summary;
      console.log("Summary data:", summary);

      isSummaryLoading = false; // Reset flag
      hideLoadingOverlay(); // Hide the overlay once loading is complete

      // Restore original content
      mainContent.innerHTML = originalContent;

      // Display summary in modal
      const summaryContent = document.getElementById("summary-content");
      summaryContent.innerHTML = ""; // Clear existing content

      // Add summary details
      const mainHeader = document.createElement("h2");
      mainHeader.textContent = "✨";
      summaryContent.appendChild(mainHeader);

      const titleElement = document.createElement("h2");
      titleElement.textContent = videoTitle;
      summaryContent.appendChild(titleElement);

      if (Array.isArray(summary.sections)) {
        summary.sections.forEach((section, index) => {
          const { header, bullets } = section;

          if (header && Array.isArray(bullets) && bullets.length === 2) {
            // Create section container
            const sectionContainer = document.createElement("div");

            // Create header element
            const headerElement = document.createElement("h3");
            headerElement.textContent = header;
            summaryContent.appendChild(headerElement);

            // Create bullet list
            const bulletList = document.createElement("ul");

            // Add bullet points
            bullets.forEach((bullet) => {
              const bulletItem = document.createElement("li");
              bulletItem.textContent = bullet;
              bulletList.appendChild(bulletItem);
            });

            sectionContainer.appendChild(bulletList);
            summaryContent.appendChild(sectionContainer);
          } else {
            // Handle missing or malformed fields
            const errorElement = document.createElement("p");
            errorElement.textContent = `Incomplete data for section ${
              index + 1
            }. Unable to display the summary.`;
            summaryContent.appendChild(errorElement);
          }
        });
      } else {
        const errorElement = document.createElement("p");
        errorElement.textContent =
          "Summary data is not in the expected format.";
        summaryContent.appendChild(errorElement);
      }

      // Set YouTube link
      const youtubeLink = document.getElementById("youtube-link");
      youtubeLink.href = `https://www.youtube.com/watch?v=${videoId}`;

      // Configure download button for PDF summary
      const downloadLink = document.getElementById("download-link");
      downloadLink.style.display = "inline-block";
      downloadLink.onclick = () => generatePDF(summary, videoTitle);

      // Show modal
      document.getElementById("summaryModal").style.display = "block";
    })
    .catch((error) => {
      isSummaryLoading = false; // Reset flag
      console.error("Error fetching summary:", error);

      hideLoadingOverlay(); // Ensure overlay is hidden

      // Restore original content
      mainContent.innerHTML = originalContent;

      alert("Failed to fetch summary. Please try again.");
    });
}

function fetchSummary(
  videoId,
  videoTitle,
  videoChannel,
  videoViews,
  videoPostDate
) {
  if (isSummaryLoading) {
    console.log("A summary is already loading. Please wait.");
    return;
  }

  isSummaryLoading = true; // Set loading flag

  // Show the loading overlay
  showLoadingOverlay();

  // Locate the target video card by `data-video-id`
  const targetCard = document.querySelector(
    `.video-card[data-video-id="${videoId}"]`
  );

  if (!targetCard) {
    console.error("Target video card not found.");
    isSummaryLoading = false; // Reset flag
    enableVideoClicks(); // Re-enable clicks
    return;
  }

  // Preserve card dimensions to prevent collapse
  const cardStyles = window.getComputedStyle(targetCard);
  const cardHeight = cardStyles.height;
  const cardWidth = cardStyles.width;

  // Explicitly set height, width, min-height, and min-width
  targetCard.style.height = cardHeight;
  targetCard.style.width = cardWidth;
  targetCard.style.minHeight = cardHeight;
  targetCard.style.minWidth = cardWidth;

  // Optionally, add a fallback to ensure dimensions for small screens
  targetCard.style.flexShrink = "0";

  // Create spinner container
  const spinnerContainer = document.createElement("div");
  spinnerContainer.className = "spinner-container";
  spinnerContainer.style.display = "flex";
  spinnerContainer.style.justifyContent = "center";
  spinnerContainer.style.alignItems = "center";
  spinnerContainer.style.height = cardHeight; // Match the card's height
  spinnerContainer.style.width = cardWidth; // Match the card's width

  // Spinner element
  const spinner = document.createElement("div");
  spinner.className = "spinner";
  spinnerContainer.appendChild(spinner);

  // Save original content
  const originalContent = targetCard.innerHTML;

  // Replace content with spinner
  targetCard.innerHTML = "";
  targetCard.appendChild(spinnerContainer);

  // Fetch summary
  fetch(`/summarize?videoId=${videoId}`)
    .then((response) => response.json())
    .then((data) => {
      if (!data || typeof data.summary === "undefined") {
        console.error("Summary data is missing or undefined.");
        alert("The server did not return valid summary data.");
        return;
      }

      // Proceed with rendering summary
      const summary = data.summary;
      console.log("Summary data:", summary);

      isSummaryLoading = false; // Reset flag
      hideLoadingOverlay(); // Hide the overlay once loading is complete
      enableVideoClicks(); // Re-enable clicks

      // Restore original content
      targetCard.innerHTML = originalContent;

      // Reattach event handler
      const thumbnail = targetCard.querySelector("img");
      thumbnail.onclick = () =>
        fetchSummary(
          videoId,
          videoTitle,
          videoChannel,
          videoViews,
          videoPostDate
        );

      // Display summary in modal
      const summaryContent = document.getElementById("summary-content");
      summaryContent.innerHTML = ""; // Clear existing content

      // Add Copy Text button with icon
      const copyButton = document.createElement("button");
      copyButton.style.display = "inline-flex";
      copyButton.style.alignItems = "center";
      copyButton.style.justifyContent = "center";
      copyButton.style.border = "1px solid #ddd";
      copyButton.style.borderRadius = "8px";
      copyButton.style.padding = "10px";
      copyButton.style.background = "#fff";
      copyButton.style.cursor = "pointer";
      copyButton.style.width = "48px";
      copyButton.style.height = "48px";

      // Create an SVG icon with larger dimensions
      const copyIcon = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "svg"
      );
      copyIcon.setAttribute("width", "32");
      copyIcon.setAttribute("height", "32");
      copyIcon.setAttribute("viewBox", "0 0 24 24");
      copyIcon.setAttribute("fill", "none");
      copyIcon.setAttribute("stroke", "currentColor");
      copyIcon.setAttribute("stroke-width", "2");
      copyIcon.setAttribute("stroke-linecap", "round");
      copyIcon.setAttribute("stroke-linejoin", "round");

      // Define paths for the icon
      const rect1 = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect"
      );
      rect1.setAttribute("x", "9");
      rect1.setAttribute("y", "9");
      rect1.setAttribute("width", "12");
      rect1.setAttribute("height", "15");
      rect1.setAttribute("rx", "2");
      rect1.setAttribute("ry", "2");

      const rect2 = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "rect"
      );
      rect2.setAttribute("x", "5");
      rect2.setAttribute("y", "5");
      rect2.setAttribute("width", "12");
      rect2.setAttribute("height", "15");
      rect2.setAttribute("rx", "2");
      rect2.setAttribute("ry", "2");

      // Add rectangles to the SVG
      copyIcon.appendChild(rect2); // Back rectangle
      copyIcon.appendChild(rect1); // Front rectangle

      // Append the SVG to the button
      copyButton.appendChild(copyIcon);

      // Append the button to the desired container
      summaryContent.appendChild(copyButton);

      // Add video info
      const titleElement = document.createElement("h2");
      titleElement.textContent = videoTitle.replace(/&#39;/g, "'");
      summaryContent.appendChild(titleElement);

      const details = document.createElement("p");
      details.textContent = `${videoChannel} • ${formatViews(
        videoViews
      )} views • ${formatPostDate(videoPostDate)}`;
      summaryContent.appendChild(details);

      const space = document.createElement("br");
      summaryContent.appendChild(space);

      if (Array.isArray(summary.sections)) {
        summary.sections.forEach((section, index) => {
          const { header, bullets } = section;

          if (header && Array.isArray(bullets) && bullets.length === 2) {
            // Create section container
            const sectionContainer = document.createElement("div");

            // Create header element
            const headerElement = document.createElement("h3");
            headerElement.textContent = header.replace(/&#39;/g, "'");
            summaryContent.appendChild(headerElement);

            // Create bullet list
            const bulletList = document.createElement("ul");

            // Add bullet points
            bullets.forEach((bullet) => {
              const bulletItem = document.createElement("li");
              bulletItem.textContent = bullet.replace(/&#39;/g, "'");
              bulletList.appendChild(bulletItem);
            });

            sectionContainer.appendChild(bulletList);
            summaryContent.appendChild(sectionContainer);
          } else {
            // Handle missing or malformed fields
            const errorElement = document.createElement("p");
            errorElement.textContent = `Incomplete data for section ${
              index + 1
            }. Unable to display the summary.`;
            summaryContent.appendChild(errorElement);
          }
        });
      } else {
        const errorElement = document.createElement("p");
        errorElement.textContent =
          "Summary data is not in the expected format.";
        summaryContent.appendChild(errorElement);
      }

      // Configure Copy Text button
      copyButton.onclick = () => {
        // Get the summary text
        const summaryText = summaryContent.innerText;

        // Create a temporary textarea element to hold the summary text
        const tempTextArea = document.createElement("textarea");
        tempTextArea.value = summaryText;
        document.body.appendChild(tempTextArea);

        // Select the text and copy it to the clipboard
        tempTextArea.select();
        document.execCommand("copy");

        // Remove the temporary textarea element
        document.body.removeChild(tempTextArea);

        // Alert the user that the text has been copied
        alert("Summary text copied to clipboard.");
      };

      // Set YouTube link
      const youtubeLink = document.getElementById("youtube-link");
      youtubeLink.href = `https://www.youtube.com/watch?v=${videoId}`;

      // Configure download button for PDF summary
      const downloadLink = document.getElementById("download-link");
      downloadLink.style.display = "inline-block";
      downloadLink.onclick = () => generatePDF(summary, videoTitle);

      // Show modal
      document.getElementById("summaryModal").style.display = "block";
    })
    .catch((error) => {
      isSummaryLoading = false; // Reset flag
      console.error("Error fetching summary:", error);

      hideLoadingOverlay(); // Ensure overlay is hidden
      enableVideoClicks(); // Re-enable clicks

      // Restore original content
      targetCard.innerHTML = originalContent;

      // Reattach event handler
      const thumbnail = targetCard.querySelector("img");
      thumbnail.onclick = () =>
        fetchSummary(
          videoId,
          videoTitle,
          videoChannel,
          videoViews,
          videoPostDate
        );

      alert("Failed to fetch summary. Please try again.");
    });
}

// Utility to enable clicks on video cards
function enableVideoClicks() {
  const videoCards = document.querySelectorAll(".video-card img");
  videoCards.forEach((img) => {
    img.style.pointerEvents = "auto"; // Re-enable clicks
  });
}

function generatePDF(summary, videoTitle) {
  const { jsPDF } = window.jspdf;

  // Debugging: Log the incoming summary object
  console.log("Generating PDF. Summary received:", summary);

  // Validate summary data structure
  if (
    !summary ||
    typeof summary !== "object" ||
    !summary.sections ||
    !Array.isArray(summary.sections)
  ) {
    alert("Invalid summary data: Sections are missing or not an array.");
    console.error("Invalid summary data structure:", summary);
    return;
  }

  const doc = new jsPDF();
  const marginX = 10;
  const marginY = 20;
  const lineHeight = 10;
  const pageWidth = 210;
  const contentWidth = pageWidth - marginX * 2;
  const pageHeight = 297;
  const pageBottomMargin = 20;
  let y = marginY;

  // Add video title
  if (videoTitle) {
    console.log("Adding video title:", videoTitle);
    doc.setFontSize(16);
    doc.setFont("helvetica", "bold");
    const titleLines = doc.splitTextToSize(videoTitle, contentWidth);
    titleLines.forEach((line) => {
      if (y + lineHeight > pageHeight - pageBottomMargin) {
        doc.addPage();
        y = marginY;
      }
      doc.text(line, marginX, y);
      y += lineHeight;
    });
    y += 5;
  }

  // Loop through sections
  summary.sections.forEach((section, index) => {
    const { header, bullets } = section;
    console.log(`Processing section ${index + 1}:`, section);

    if (header && Array.isArray(bullets)) {
      doc.setFontSize(14);
      doc.setFont("helvetica", "bold");
      const headerLines = doc.splitTextToSize(header, contentWidth);
      headerLines.forEach((line) => {
        if (y + lineHeight > pageHeight - pageBottomMargin) {
          doc.addPage();
          y = marginY;
        }
        doc.text(line, marginX, y);
        y += lineHeight;
      });

      doc.setFontSize(12);
      doc.setFont("helvetica", "normal");
      bullets.forEach((bullet) => {
        const bulletLines = doc.splitTextToSize(`• ${bullet}`, contentWidth);
        bulletLines.forEach((line) => {
          if (y + lineHeight > pageHeight - pageBottomMargin) {
            doc.addPage();
            y = marginY;
          }
          doc.text(line, marginX + 5, y);
          y += lineHeight;
        });
      });
    } else {
      console.error(
        `Incomplete or invalid section data for section ${index + 1}:`,
        section
      );
    }
  });

  // Save the PDF
  const filename = videoTitle ? `${videoTitle}.pdf` : "summary.pdf";
  doc.save(filename);
}

function closeModal() {
  document.getElementById("summaryModal").style.display = "none";
}

window.onclick = function (event) {
  const modal = document.getElementById("summaryModal");
  if (event.target == modal) {
    modal.style.display = "none";
  }
};

function showLoadingOverlay() {
  let overlay = document.getElementById("loading-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "loading-overlay";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
    overlay.style.zIndex = "9999";
    overlay.style.display = "flex";
    overlay.style.justifyContent = "center";
    overlay.style.alignItems = "center";
    overlay.innerHTML = `<div class="spinner"></div>`;
    document.body.appendChild(overlay);
  }
  overlay.style.display = "flex"; // Ensure overlay is visible
}

function hideLoadingOverlay() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) {
    overlay.style.display = "none"; // Hide overlay
  }
}
