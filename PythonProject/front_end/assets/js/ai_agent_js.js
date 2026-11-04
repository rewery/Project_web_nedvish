
const textarea = document.getElementById("message");

textarea.addEventListener("input", () => {
  textarea.style.height = "auto";
  textarea.style.height =
    Math.min(textarea.scrollHeight, 200) + "px";
});

textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

function sendMessage() {
  const message = textarea.value.trim();

  if (!message) return;

  console.log("Сообщение:", message);

  textarea.value = "";
  textarea.style.height = "auto";
}