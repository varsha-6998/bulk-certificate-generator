const recipientList = document.querySelector("#recipient-list");
const addRecipientButton = document.querySelector("#add-recipient");
const form = document.querySelector("#certificate-form");
const result = document.querySelector("#result");

function addRecipient(name = "", email = "") {
  const row = document.createElement("div");
  row.className = "recipient-row";
  const nameInput = document.createElement("input");
  nameInput.name = "recipient-name";
  nameInput.placeholder = "Recipient name";
  nameInput.autocomplete = "name";
  nameInput.maxLength = 120;
  nameInput.value = name;
  nameInput.setAttribute("aria-label", "Recipient name");

  const emailInput = document.createElement("input");
  emailInput.name = "recipient-email";
  emailInput.type = "email";
  emailInput.placeholder = "Email address";
  emailInput.autocomplete = "email";
  emailInput.maxLength = 254;
  emailInput.value = email;
  emailInput.setAttribute("aria-label", "Recipient email");

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "remove-button";
  removeButton.textContent = "×";
  removeButton.setAttribute("aria-label", "Remove recipient");
  removeButton.addEventListener("click", () => {
    row.remove();
    if (!recipientList.children.length) addRecipient();
  });

  row.append(nameInput, emailInput, removeButton);
  recipientList.append(row);
}

addRecipientButton.addEventListener("click", () => addRecipient());
addRecipient();

function showMessage(kind, heading, message) {
  result.hidden = false;
  result.className = `result ${kind}`;
  result.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = heading;
  const text = document.createElement("p");
  text.textContent = message;
  result.append(title, text);
}

function displayJob(job) {
  result.hidden = false;
  result.className = `result ${job.status === "COMPLETED" ? "success" : job.status === "PARTIAL" ? "partial" : "error"}`;
  result.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = job.status === "COMPLETED"
    ? "Certificates generated successfully"
    : job.status === "PARTIAL"
      ? "Certificate batch partially completed"
      : "Certificate generation failed";
  const summary = document.createElement("p");
  summary.textContent = `Job ID: ${job.id} · ${job.successful} successful · ${job.failed} failed · ${job.total} total`;
  const list = document.createElement("div");
  list.className = "certificate-list";

  for (const certificate of job.certificates) {
    const item = document.createElement("div");
    item.className = "certificate-item";
    const recipient = document.createElement("span");
    recipient.textContent = `${certificate.recipient_name} (${certificate.recipient_email})`;
    const status = document.createElement("span");
    status.className = `certificate-status ${certificate.status.toLowerCase()}`;
    status.textContent = certificate.status;
    item.append(recipient, status);
    if (certificate.status === "COMPLETED") {
      const link = document.createElement("a");
      link.href = certificate.download_url;
      link.textContent = "Download PDF";
      link.setAttribute("aria-label", `Download certificate for ${certificate.recipient_name}`);
      item.append(link);
    } else if (certificate.error_message) {
      const error = document.createElement("span");
      error.className = "certificate-error";
      error.textContent = certificate.error_message;
      item.append(error);
    }
    list.append(item);
  }

  result.append(heading, summary, list);
  if (job.successful > 0) {
    const zip = document.createElement("a");
    zip.className = "zip-link";
    zip.href = `/jobs/${job.id}/download`;
    zip.textContent = "Download successful certificates (.zip)";
    result.append(zip);
  }
}

async function readError(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `Request failed (${response.status}).`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  const csvFile = document.querySelector("#csv-file").files[0];
  const eventName = document.querySelector("#event-name").value.trim();
  const eventDate = document.querySelector("#event-date").value;
  if (!eventName || !eventDate) {
    showMessage("error", "Check the event details", "Enter an event name and date.");
    return;
  }

  button.disabled = true;
  button.textContent = "Generating certificates…";
  showMessage("", "Working on it", "Your certificates are being generated. Please wait.");

  try {
    let response;
    if (csvFile) {
      const data = new FormData();
      data.append("event_name", eventName);
      data.append("event_date", eventDate);
      data.append("file", csvFile);
      response = await fetch("/jobs/csv", { method: "POST", body: data });
    } else {
      const names = [...recipientList.querySelectorAll('[name="recipient-name"]')];
      const emails = [...recipientList.querySelectorAll('[name="recipient-email"]')];
      const recipients = names.map((input, index) => ({
        name: input.value.trim(),
        email: emails[index].value.trim(),
      })).filter((recipient) => recipient.name || recipient.email);
      response = await fetch("/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_name: eventName, event_date: eventDate, recipients }),
      });
    }
    if (!response.ok) throw new Error(await readError(response));
    displayJob(await response.json());
  } catch (error) {
    showMessage("error", "Generation failed", error.message || "Please try again.");
  } finally {
    button.disabled = false;
    button.textContent = "Generate certificates";
  }
});
