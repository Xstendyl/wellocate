"""One frozen decision round sent straight to a model through OpenRouter, with no Wellocate code.

Each seed builds a seven-round history on a simple additive landscape. The model picks four candidates for round 8
under three prompts: A, exact readings stated; B, exactness not stated; C, noisy readings stated.
Usage: OPENROUTER_API_KEY=... python3 indep_vignette.py [N_SEEDS] [MODEL] [COST_CAP_USD]
"""
import json, os, random, re, sys, time, urllib.request
N=int(sys.argv[1]) if len(sys.argv)>1 else 30
MODEL=sys.argv[2] if len(sys.argv)>2 else 'anthropic/claude-opus-4.7'
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'rerun')
os.makedirs(OUT, exist_ok=True)
CAP=float(sys.argv[3]) if len(sys.argv)>3 else 3.0
AL='ABCDEFGHIJKLMNOPQRST'
def key():
    return os.environ['OPENROUTER_API_KEY']
def call(prompt):
    body=json.dumps({"model":MODEL,"temperature":0,"max_tokens":400,"messages":[{"role":"user","content":prompt}]}).encode()
    req=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",data=body,
        headers={"Authorization":"Bearer "+key(),"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=180) as r: d=json.loads(r.read().decode())
    ch=d["choices"][0]; return ch["message"]["content"] or "", ch.get("finish_reason"), float((d.get("usage") or {}).get("cost") or 0)
def world(seed):
    r=random.Random(seed); w=[[r.gauss(0,0.35) for _ in AL] for _ in range(4)]
    def true(s): return 6.0+sum(w[i][AL.index(c)] for i,c in enumerate(s))
    return r,true
def history(seed):
    r,true=world(seed); start=''.join(r.choice(AL) for _ in range(4))
    hist=[]; measured=set()
    def mut(s):
        i=r.randrange(4); c=r.choice([x for x in AL if x!=s[i]]); return s[:i]+c+s[i+1:]
    # rounds 1..7, 4 orders each, all distinct except one planned repeat of the champion in round 6
    cur=start
    for rnd in range(1,8):
        picks=[]
        while len(picks)<4:
            if rnd==1 and not picks: q=start
            else:
                base=max(measured|{start},key=true) if measured else start
                q=mut(base if r.random()<0.7 else ''.join(r.choice(AL) for _ in range(4)))
            if q not in measured and q not in picks: picks.append(q)
        if rnd==6:
            champ=max(measured,key=true); picks[0]=champ
        for q in picks: hist.append((rnd,q)); measured.add(q)
    return hist,true,r
def render(seed,arm):
    hist,true,r=history(seed); nr=random.Random(seed*7+1)
    rows=[]
    for rnd,q in hist:
        t=true(q)
        v=t if arm in('A','B') else t+nr.gauss(0,0.07*t)
        rows.append('%5d  %s  %.3f'%(rnd,q,v))
    noise={'A':"Measurements are EXACT: measuring the same candidate again always returns exactly the same number.",
           'B':"",
           'C':"Measurements are NOISY: each reading is the true score plus random error of about 7% of the score, so measuring the same candidate again gives a different reading."}[arm]
    p=("You are choosing which candidates to measure in an optimization task.\n\n"
       "Each candidate is a 4-letter string; each position holds one of 20 letters (A to T). "
       "Every candidate is valid: no order is ever rejected or lost. Each measurement returns a numeric reading of the candidate's score.\n"
       +(noise+"\n" if noise else "")+
       "\nBUDGET: 15 rounds of 4 measurements, 60 in total. 7 rounds are done, 28 measurements used, 32 remain.\n"
       "GOAL: after the last round you will name ONE candidate. You are scored only on that candidate's TRUE score. "
       "The measurements themselves earn nothing.\n\nHISTORY (round, candidate, reading)\n"+"\n".join(rows)+
       "\n\nChoose 4 candidates to measure in round 8. Reply with exactly 4 lines and nothing else, each:\nCANDIDATE | one short reason\n")
    measured={q for _,q in hist}
    champ_by_read=max(set(q for _,q in hist),key=lambda q: sum(float(x.split()[2]) for x in rows if x.split()[1]==q)/sum(1 for x in rows if x.split()[1]==q))
    return p,measured,champ_by_read
def main():
    res=[]; spend=0.0
    for seed in range(1,N+1):
        for arm in 'ABC':
            p,measured,champ=render(seed,arm)
            txt,fin,cost=call(p); spend+=cost
            orders=re.findall(r'^\s*([A-T]{4})\s*\|',txt,re.M)[:4]
            res.append(dict(seed=seed,arm=arm,orders=orders,repeats=sum(o in measured for o in orders),
                            champ_reordered=champ in orders,finish=fin,cost=cost,text=txt,prompt=p if seed==1 else None))
            json.dump(res,open(os.path.join(OUT,'results_raw_%s.json'%MODEL.split('/')[1]),'w'))
            if spend>CAP: print('budget cap reached'); return
    print('done calls',len(res),'spend $%.3f'%spend)
if __name__=='__main__': main()
