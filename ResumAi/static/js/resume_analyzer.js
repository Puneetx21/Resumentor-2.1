const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const selectedFile = document.getElementById('selectedFile');

function setSelectedFileName(file) {
    if (!file) {
        selectedFile.textContent = '';
        selectedFile.classList.remove('show');
        return;
    }
    selectedFile.innerHTML = `<i class="fas fa-check-circle"></i> Selected: ${file.name}`;
    selectedFile.classList.add('show');
}

fileInput.addEventListener('change', function(event) {
    const file = event.target.files && event.target.files[0];
    setSelectedFileName(file);
});

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput.click();
    }
});

dropZone.addEventListener('dragover', event => {
    event.preventDefault();
    dropZone.classList.add('active');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('active');
});

dropZone.addEventListener('drop', event => {
    event.preventDefault();
    dropZone.classList.remove('active');
    const files = event.dataTransfer.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        selectedFile.textContent = 'Please select a PDF file only.';
        selectedFile.classList.add('show');
        return;
    }

    fileInput.files = files;
    setSelectedFileName(file);
});
