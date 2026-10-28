const input = document.getElementById("videoInput");

input.addEventListener("change", function () {

    if (this.files.length > 0) {

        alert("Selected: " + this.files[0].name);

    }

});