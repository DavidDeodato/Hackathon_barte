import {useCallback,useEffect,useState,type ReactNode} from 'react';
import {ArrowRight,Layers3,LoaderCircle,LockKeyhole} from 'lucide-react';
import './access.css';

type Session={authenticated:boolean;required:boolean};
const accessError=(error:unknown,fallback:string)=>error instanceof Error&&error.name==='Error'?error.message:fallback;
export default function AccessGate({base,children}:{base:string;children:(onSignOut?:()=>void)=>ReactNode}){
  const [session,setSession]=useState<Session|null>(null);
  const [password,setPassword]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const endpoint=`${base.replace(/\/$/,'')}/api/session`;
  const check=useCallback(async(signal?:AbortSignal)=>{
    setError('');
    try{
      const response=await fetch(endpoint,{credentials:'same-origin',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error('Não foi possível abrir seu espaço. Tente novamente.');
      const data=await response.json();
      if(typeof data.authenticated!=='boolean'||typeof data.required!=='boolean')throw new Error('Não foi possível abrir seu espaço. Tente novamente.');
      if(!signal?.aborted)setSession(data);
    }catch(e){if(!signal?.aborted)setError(accessError(e,'Não foi possível abrir seu espaço. Confira sua conexão e tente novamente.'));}
  },[endpoint]);
  useEffect(()=>{const controller=new AbortController();void check(controller.signal);const expired=()=>{setSession({authenticated:false,required:true});setPassword('');setError('Sua sessão terminou. Entre novamente para continuar.');};window.addEventListener('lastro:session-expired',expired);return()=>{controller.abort();window.removeEventListener('lastro:session-expired',expired);};},[check]);
  async function signIn(){
    if(!password.trim()||busy)return;
    setBusy(true);setError('');
    try{
      const response=await fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password}),signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error([401,403].includes(response.status)?'Senha incorreta. Confira e tente novamente.':response.status===429?'Muitas tentativas. Aguarde um momento e tente novamente.':'Não foi possível entrar agora. Tente novamente.');
      setPassword('');await check();
    }catch(e){setError(accessError(e,'Não foi possível entrar agora. Confira sua conexão e tente novamente.'));}finally{setBusy(false);}
  }
  async function signOut(){
    try{const response=await fetch(endpoint,{method:'DELETE',credentials:'same-origin',signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error();setSession({authenticated:false,required:true});setError('');setPassword('');}
    catch{setError('Não foi possível sair. Tente novamente.');}
  }
  if(session&&(session.authenticated||!session.required))return <>{children(session.required&&session.authenticated?()=>void signOut():undefined)}{error&&<div className="access-toast" role="alert">{error}<button onClick={()=>void signOut()}>Tentar novamente</button></div>}</>;
  return <main className="access-screen"><section className="access-card"><div className="access-brand"><Layers3 size={27}/><span>LASTRO</span></div><div className="access-mark"><LockKeyhole size={24}/></div><h1>Seu fechamento,<br/>com tudo no lugar.</h1><p>Documentos, apuração e decisões em um só espaço.</p>{!session?<><div className="access-loading" role="status">{!error&&<LoaderCircle className="spin" size={18}/>} {error||'Abrindo seu espaço…'}</div>{error&&<button className="button primary" onClick={()=>void check()}>Tentar novamente</button>}</>:<form onSubmit={e=>{e.preventDefault();void signIn();}}><label htmlFor="access-password">Senha de acesso</label><input id="access-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" autoFocus required disabled={busy}/>{error&&<p role="alert" className="access-error">{error}</p>}<button className="button primary" disabled={busy||!password.trim()}>{busy?<LoaderCircle className="spin" size={17}/>:<ArrowRight size={17}/>} {busy?'Entrando…':'Acessar Lastro'}</button></form>}</section><div className="access-aside" aria-hidden="true"><span>DA ORIGEM<br/>À DECISÃO.</span><div className="access-orbit"/></div></main>;
}
