const scoreValueEl=document.getElementById('scoreValue');
const clickBtn=document.getElementById('clickBtn');
const saveBtn=document.getElementById('saveBtn');
const resetBtn=document.getElementById('resetBtn');
const leaderList=document.getElementById('leaderList');
const playerNameEl=document.getElementById('playerName');

let scoreValue=Number(localStorage.getItem('scoreValue')||0);
let playerName=localStorage.getItem('playerName')||'';
playerNameEl.value=playerName;

function updateScore(){scoreValueEl.textContent=String(scoreValue);}
updateScore();

clickBtn.addEventListener('click',()=>{scoreValue++;updateScore();localStorage.setItem('scoreValue',String(scoreValue));});
resetBtn.addEventListener('click',()=>{scoreValue=0;updateScore();localStorage.setItem('scoreValue','0');});
playerNameEl.addEventListener('input',()=>{playerName=playerNameEl.value;localStorage.setItem('playerName',playerName)});

async function fetchHighScores(){
  try{
    const res=await fetch('/api/highScores');
    const data=await res.json();
    leaderList.innerHTML='';
    data.highScores.forEach((row,i)=>{
      const li=document.createElement('li');
      li.textContent=`#${i+1} ${row.playerName} — ${row.scoreValue}`;
      leaderList.appendChild(li);
    });
  }catch(err){console.error(err)}
}

function getCookie(name){
  const value=`; ${document.cookie}`;
  const parts=value.split(`; ${name}=`);
  if(parts.length===2) return parts.pop().split(';').shift();
}

saveBtn.addEventListener('click',async()=>{
  try{
    const csrf=getCookie('csrftoken');
    await fetch('/api/saveScore',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf||''},body:JSON.stringify({playerName:playerNameEl.value||'Anonymous',scoreValue})});
    await fetchHighScores();
  }catch(err){console.error(err)}
});

fetchHighScores();
setInterval(fetchHighScores,15000);
