const counters = document.querySelectorAll(".counter");

counters.forEach(counter => {

    const target = +counter.dataset.target;

    const update = () => {

        const current = +counter.innerText;

        const increment = target / 150;

        if(current < target){

            counter.innerText = Math.ceil(current + increment);

            requestAnimationFrame(update);

        }else{

            if(target >= 1000000){

                counter.innerText = (target/1000000) + "M+";

            }else if(target >=10000){

                counter.innerText = (target/1000) + "K+";

            }else{

                counter.innerText = target;

            }

        }

    };

    update();

});

document.querySelectorAll(".feature-card").forEach(card=>{

card.addEventListener("mousemove",(e)=>{

const rect=card.getBoundingClientRect();

const x=e.clientX-rect.left;

const y=e.clientY-rect.top;

card.style.background=
`radial-gradient(circle at ${x}px ${y}px,
rgba(124,58,237,.20),
rgba(17,24,39,.95))`;

});

card.addEventListener("mouseleave",()=>{

card.style.background="rgba(255,255,255,.05)";

});

});

const faqItems=document.querySelectorAll(".faq-item");

faqItems.forEach(item=>{

const btn=item.querySelector(".faq-btn");

btn.addEventListener("click",()=>{

item.classList.toggle("active");

});

});