#!/usr/bin/env python3
"""
THE DAILY DISPATCH — Saturday, 21 November 2026 in one image.

Deterministic newspaper front-page generator for the make.fun bounty
"Sum up 21 November's world news in one image" (news-image-20261121).

Pure Python 3 standard library: no third-party libraries, no font files, no
input files at all. The Liberation typefaces are carried inside this
file as an embedded glyph atlas (bitmap masks + advances + kerning,
zlib-compressed and base85-encoded below); a small raster engine blits
those glyphs onto an RGB canvas and writes the PNG itself.

- All news content is embedded below as data (compiled from Reuters, AP,
  BBC, NYT and wire reports dated 21 November 2026; summaries condensed
  from the full list in stories.md).
- Writes exactly one PNG to $MAKEFUN_OUTPUT_DIR/entry.png (default
  /output/entry.png), at most 1024x1024 and at most 1 MiB.
- Two runs produce byte-identical output: fixed layout algorithm (the
  column packer picks the first size preset that fits), fixed zlib
  level, per-row PNG filters chosen by a fixed scoring rule, and no
  timestamps, randomness or environment-dependent data anywhere.
"""

import math
import os
import struct
import zlib
from base64 import b85decode

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
PAPER = (250, 247, 238)
INK = (18, 18, 18)
GREY = (70, 70, 70)
DARK = (40, 40, 40)
ACCENT = (150, 30, 20)      # deep red for kickers / thermometer
GLOBE_LAND = (96, 128, 92)
GLOBE_SEA = (196, 214, 222)
WHITE = (255, 255, 255)

W, H = 1024, 1024
M = 26                      # page margin
CW = W - 2 * M              # content width = 972
COL_W = 316
COL_X = [M, M + COL_W + 12, M + 2 * (COL_W + 12)]
COL_BOTTOM = H - 36

# --------------------------------------------------------------------------
# News data — every story dated Saturday, 21 November 2026
# (headline, one-line summary with source)
# --------------------------------------------------------------------------
HERO_KICKER = "CLIMATE SUMMIT \u00b7 ANTALYA, TURKEY"
HERO_HEADLINE = "COP31 TALKS RUN DEEP INTO OVERTIME OVER FOSSIL FUELS"
HERO_SUMMARY = (
    "ANTALYA \u2014 Negotiators from nearly 200 countries worked through Saturday with no final "
    "deal, after a draft text dropped every mention of the fossil fuels driving global warming. "
    "Crews were already boxing up the venue as delegations shuttled between rooms; the EU's "
    "climate chief Wopke Hoekstra warned it would be \u201ca good deal or no deal.\u201d"
)
HERO_BYLINE = "Reuters / AP \u2014 Antalya"
HERO_CAPTION = (
    "A feverish planet: October ran 1.8\u00b0C above pre-industrial levels, Berkeley Earth says, "
    "in a year of heatwaves and floods."
)

# markets strip is built from segments; trailing segments are dropped
# (deterministically) until the line fits the bar
STRIP_SEGMENTS = [
    "MARKETS \u2014 AI SELL-OFF RATTLES THE WORLD:",
    "S&P 500 \u22123.7%", "NIKKEI \u22125.1%", "FTSE \u22121.0%", "GOLD \u22124.6%",
    "BITCOIN $57,850", "BRENT $89.95 \u25b2", "SENSEX +2.3%",
]

SECTIONS = [
    ("EUROPE", [
        ("Russia fires 400 drones and 110 missiles at Ukraine",
         "Projectiles land in Poland; at least 8 killed in Kyiv, power cut in 10 regions. (BBC)"),
        ("Trump tells Europe to defund Ukraine after Putin summit",
         "Angry call after the summit; Zelensky calls Putin a \u201ckiller.\u201d (Telegraph)"),
        ("UK and EU sign three post-Brexit agreements",
         "Burnham signs youth mobility, trade and energy deals in Brussels. (Wires)"),
        ("Denmark expels Russian diplomat over plot to kill rapper",
         "Two arrested over plot against a US-Ukrainian rapper. (Wires)"),
        ("Cost-of-living protests spread across Europe",
         "Students in 25 countries walk out over costs, tuition, military spending. (Wires)"),
        ("Spain heads to snap election on Nov. 29",
         "Banking tax to be extended to fund housing, PM says. (Wires)"),
        ("Activists brand COP31 among worst ever",
         "100 groups warn hosts Turkey and Australia of a historic low point. (AP)"),
    ]),
    ("MIDDLE EAST", [
        ("Saudi defences destroy three Houthi missiles over Riyadh",
         "Interceptions confirmed after 2am; emergency alerts issued, then lifted. (Reuters)"),
        ("Tankers hit near Hormuz as US\u2013Iran talks stall",
         "Iran's Guards say they downed a US drone over the strait. (Wires)"),
        ("Trump weighs new strikes on Iran; Israel presses for action",
         "New intelligence on Iranian capabilities drives the talks. (NYT)"),
        ("Israeli fire kills Palestinians in Gaza",
         "Seven reported killed across the Strip despite the ceasefire. (Wires)"),
        ("Saudi Arabia, Japan agree oil stockpile deal",
         "Riyadh to triple crude stored in Japan amid tensions. (Arab News)"),
    ]),
    ("ASIA-PACIFIC", [
        ("Japan sidelined by China as ties hit record low",
         "Beijing: Japan must change its \u201cattitude\u201d after Xi snubs PM Takaichi at APEC. (Wires)"),
        ("India, Japan deepen defence ties at Tokyo 2+2",
         "Japanese forces to train at Indian ranges; ISRO\u2013JAXA space pact signed. (Wires)"),
        ("UN court: Myanmar responsible for Rohingya genocide",
         "ICJ ruling draws protests from Myanmar and China. (Wires)"),
        ("Japan core inflation rises to 2.2% in October",
         "Figure keeps pressure on Tokyo policymakers. (Wires)"),
        ("Pilotless air taxi carries passenger in Japan",
         "Uncrewed first in Yamanashi Prefecture. (Wires)"),
        ("Nepal PM Balendra Shah to visit India",
         "Trip to anchor a reset in Kathmandu\u2013Delhi ties. (Wires)"),
    ]),
    ("AMERICAS", [
        ("Magnitude 6.7 earthquake shakes Peru's Andes",
         "Struck near Jun\u00edn, felt in Lima; residents fled to streets; no deaths reported. (AP)"),
        ("Anthropic lists on Wall Street at $2 trillion value",
         "AI firm's debut makes it one of the world's most valuable firms. (NYT)"),
        ("FBI criminal database and USDA reportedly hacked",
         "Intruders hit the FBI crime database and a USDA payment system. (Wires)"),
        ("Man convicted of starting deadly Palisades fire",
         "Los Angeles jury finds defendant guilty over the blaze. (Wires)"),
        ("Salvadoran troops fight gangs in Haiti, lose soldiers",
         "Casualties in clashes around Port-au-Prince. (Wires)"),
        ("Bolsonaro hospitalized in Bras\u00edlia",
         "Former president admitted with intestinal obstruction. (Wires)"),
    ]),
    ("AFRICA", [
        ("Phumzile Mlambo-Ngcuka, SA's first woman deputy president, dies at 71",
         "Death of the former UN Women chief announced by the Presidency. (Wires)"),
        ("WHO keeps Congo Ebola outbreak a global emergency",
         "Cases hit 11,613 with 5,678 deaths; children hit hardest. (WHO)"),
        ("Uganda restricts gatherings, travel over Ebola",
         "Kampala tightens measures as the outbreak grows. (Wires)"),
        ("Boat of funeral mourners capsizes in Nigeria",
         "Four dead in Bayelsa State; search continues. (Wires)"),
        ("Kenya begins onshore crude drilling in Turkana",
         "First onshore campaign opens a new energy frontier. (Wires)"),
        ("Somalia orders UAE ambassador out in 72 hours",
         "Expulsion amid a widening diplomatic row. (Wires)"),
    ]),
    ("SCIENCE & HEALTH", [
        ("Pill makes pancreatic tumours vanish in some patients",
         "Daily pill daraxonrasib left cancer undetectable in 1 in 12 trial patients. (Wires)"),
        ("BepiColombo reaches Mercury orbit after eight years",
         "European-Japanese probe ends its long cruise. (Wires)"),
        ("Voyager 1 now 24 light-hours from Earth",
         "NASA's farthest probe widens its record. (Wires)"),
        ("CERN finds first evidence of ultra-rare decay",
         "Milestone observation reported in Geneva. (Wires)"),
        ("US loses measles elimination status",
         "Designation withdrawn after sustained outbreaks. (Wires)"),
        ("Nations to draft rules for AI \u201ckiller robots\u201d by 2028",
         "States agree controls on autonomous weapons. (Wires)"),
    ]),
]

BUSINESS_BRIEF = (
    "BUSINESS \u2014 GTA 6 smashes records with nearly $4.9 billion in first-day sales \u2022 "
    "Judge endorses $7.25 billion Roundup settlement \u2022 Egypt reaches IMF staff deal "
    "unlocking about $2.3bn \u2022 Argentina's country risk tops 1,000 points \u2022 Italy gives "
    "Tesla self-driving conditional approval"
)
SPORT_BRIEF = (
    "SPORT \u2014 Verstappen takes Las Vegas GP pole after Antonelli penalty \u2022 Harry Kane "
    "to miss a few months with ankle injury \u2022 Harden passes Kobe Bryant on NBA 50-point "
    "games list \u2022 Alcaraz beats Cobolli at ATP Finals \u2022 BTS wins five MAMA awards in "
    "Osaka \u2022 Choi Min-jeong wins third straight World Tour 1,000m title"
)

FOOTER = ("THE DAILY DISPATCH \u00b7 Saturday, 21 November 2026 \u00b7 Compiled from Reuters, AP, BBC, AFP, "
          "the New York Times and wire reports \u00b7 Every story dated 21 November 2026")

# --------------------------------------------------------------------------
# Embedded font atlas.
#
# ATLAS_B85 is the zlib-compressed, base85-encoded concatenation of every
# glyph's 8-bit coverage mask. FONT_TABLE maps a font key to its glyph
# records {char: (advance, offset_x, offset_y, width, height, blob_start)}
# — advances and kerning in 1/64 px, offsets from the text anchor (left of
# the advance, top of the ascender), exactly as the typefaces measure —
# plus its pairwise kerning table {"AB": kern, ...} for pairs that occur.
# The faces are Liberation Serif / Serif Bold / Serif Italic / Sans /
# Sans Bold at the sizes the layout uses.
# --------------------------------------------------------------------------
ATLAS_B85 = (
    'c-riJcVHF8_VC`DUVson=pCd8(u;Hyl`04*MNyF^ReBKwM5IXXNLNq+0R@pRML;^zYiJ<}At43Qlbbu=&Q95x+1b4pzNgRUFY^cN'
    'opUC;J3Djc^rI+hTLe%$t<W|OcWu|ZKEhpJ>s_sI*XMdyb=>u_-c=BHwbQ%o4%Agg?@}J3uHsDBIn?FNbp5LJJZ5^7m0H&&wrh&k'
    'wU6x@pmlxAc6HFYX0Tl^Yh6Rwu2Nc87q-h+>uSPwDG9La1+MEV?8?P;9Z-8xxE|#@wJVJ8nx%Ff;k$;bU7Pr>ch#;1eAg>#*I2%*'
    'qT2N#-xZ{GwNU;e&HsyA84p(#V|sF<j}}{5?^=u(z(pJBu|2_EpgJ8#dO%wXEc&-D*~B}>y~I6NSZ4H^66~XXjt2e!uLq&)T`asS'
    '>YE6!Uqjb(S$GZ9*BM?HN7sE>cz{#u)1JbXqFp!U=IR0L%J$W+|J2~29DE<_x`VENfY<T-Tx;9(S9CoIULWJ(+Dpx5US<^!*IueO'
    'vrR|xaP6fUF)!1Whifktf`5do*JXvp@F%k|)tAZe5a8-d9VOQb0k|wKCiSIOlIwv0Y*unwPRnV`4t%QaI!x3Wsh5AUz;X=5fTUnG'
    '3w&Gc_zhpLR<8%Kz%O;Wp%JD=ig4h*hc3M`0C47JfsrckMRZwBy}ZT3Le!2lOagj{rx&C}r||Ux_4-p5IFjKqepjzsipS;0%=u7|'
    '1zuJ=>Y>ZB>SeTc)exAshR+WyHePG+@c9K@j!#mr=fI0%#-|TdDXPPVeb{&vSX5^_uCuVBYDWUT?yFvJVSz2xj^CN{a54)VrFJaF'
    '*GJUrcUa&$hBHglza47l)s6<}vV?k>>BYc2)lU!dpzF5k<rUojSI+Gt^=c)W*stJP!jr7ctsS04MbI-e<5^e4^2Fimq3ZPt@t8k='
    'ufI{R2e7~y%%OilpAOXa=$w>yrn(aXSzxrzrBoMpLLs#y%SYb{KZ+ld@UHXK>v1e_tlF_2UmsSlTeHB8%n_cTPX}t()s8pNWl6}6'
    'nNXB7!Up=QfiI5PdL>I`f$tpuc~S4$zAUKS8GaFDt<xFSty+&$9T|(EhX^d6#%0G2$P4dTVBmEYXg>yj-7iia$a9oK2lm$f&TGum'
    'uG4{GfP6#(>`#F&Y6HJ#fz>JST@AR51$rbC;4lsN6E{OeO5&Lsjks7J>GbtSZ#`8CY>Ve)hMxpjg3M>+uq(!|a*LgD5%?(!yg4K{'
    '&-vfuzSh&(g<0sE!j4Xx%zo=3;)cIkfq@Rr6rc&USvLHb0DWAPyYVR=x{H6MCYv2Bw6SsB>TRtN_}2Gic)V=IS3HfOC1u+o07GAu'
    '?v+{y*g?I_6BHnBq}v*>lSa1x6oLCSU^5Mv=`8>cXuyhy;MWj<m$V7AAz&{a=%amxjrgco%mb0=+z11sO0q!vSzY*shfG`_FAB72'
    'LQHfK3IyQc{N_Fyu;yNE1H8=0)37=2skA;yyS!44Q1~xSJNWM$(chDq)4(PJ=I^`|0S}35KYv-@_K%=_O5VZS?mWqeIzF|E47!@k'
    'wy}MZNM6&qF3<plT9`*6(t!)LF^BeL!T-<Y6`(<oeS1qf5DCL?s>?Ek3e8OWR_*&vI?z-5QoG^hbaa**NY%q&=}5Gs2I`_VcZ1-E'
    'MuC*H<r;cZ!lLSjKV=xdG5J<VbAVPAqGx4vV0%b3gG@%E<(W^rK21*&d?Z0;pp_X9pRHjBQvMKtx49#ImD$2VS|{MA{rFA0{(!(b'
    'sXxMVo32Ui`(stq5$(DohUAY?f4puka>Qxa`5Ed+$k&g&F3`}9YuFX2wt%Ykx~P};a#@UAsNcs&d-536U*NI2m|w9HklxVMcXhSP'
    'HK_k5hAEae`&~dpq&eEidh|HI9bhe$wbSs`eN-n6P=2kTI&sb>t^~T7+Wy?XOMA;RXsvBmFXy|K1&2`OSoT`<fFD4X#UJsf@2$TP'
    'ml<<m(W|ndA;WgxPf3e7@;N?r3#*Gc8|~9pcPT~vy_D;R_?1eI-8FiA{uk}3qF;115Gs?eYb&{;HfdATudDG~7k#V;7F9{11AUvF'
    '5dV=kUi|_mZ*04%uD4`1{Z2lq2HmltK}PY455tCyVRn5Hi-E<}$#7uaWsQd2UAx|_UAMQ8^Pwv6OGbzzoc~hodZ_uxe(-Gw3vf}x'
    'Zm#Hy`g7BPB~{rqi?9cX{na=MBohHJ)AU&naDVqaLks8X3RPJf2p5blWFBUezst1iPfP}uNmixPs`~F08a5KmkfdNjd~NU^pD`VM'
    'HSF<>O16N>Zc{;LSq`IEHsy}|wKM08d|)|sfn`)SY#I>nONE8ra)NZ!sLQXE4)JHHLW6c#o$-{8gr<U%qVBba_PiH<d8#o>FGvTL'
    'SGQt%MI(KCKxx9hqVi`wZqz2DBkQ9d!=7YDpPkdt<Wu^*z4$~#QdZoppU0JTO>R6!K4w_Houyr%=fR>vOc-JoQ(m$D>j*tsrP{^N'
    'QI}HQ3LhI0w0-;nQvUC-!oP!r8T4h&B6hBTIeJC(=a1>C3egP3w>E%%gn8)K2y^`R5yo%qnF}VF<71HyYkt<FU;WJS>*CWXn4y;7'
    'Rdf8@h)F>_O@8#nqCG6;6A?ym%?qnAtzVZ&-vE4}E@^bH-|bfTfq1cHcbb5n=5Q|S^){B*U(ED%u|B;RS=I3!+LIpx3yHj31_As^'
    'Oj}*E81yIkxIf?f8ik}#9csX<t58?!pz7S~zj=qfb7ofx=z?#_Kl@5N`{e%4fh=7Yk7JKb*q-d$E}h(hthH$pnRza@7^+kFS_&Dk'
    '5Xo^{v>#_#^jg_K7d9GF&ggqDYKFx`o;9_p508G;q*P_6%0305t;~`myc)qAqQ!bh1{}+a_uV1(&wmIQTcM_mzE1{REQC(0_avrC'
    'pwp+~H_3oIn#L=fRmLh`V;E!cEO?PyIQ-GM2KUxr1u9lia^H``pN_kmvz@sP>-g_TDWSla`0b|neR=!}xce8r+j}b=@D(qzU%@+3'
    'p!gyBaj=<tgO0fOFn2;$4P##U1ZRBRLexe24l4C^1~;X5E3pULHnQbrHVgF%D%)t>0kjdeO~@t#5{K2(nOP6bI3Tur>fzBMQU9I6'
    '(9?on-Qkh5e{H9|PWc;pAGfNNY6BJ@y!r5{BPsmit}ohzm{T6S;MVctzOH-5w(gFUXrMiz&w$1fIK24{byKiaZxdF?48a!NL$E!+'
    'EZCa!^0wt@!IpeTupKYUF%bR(o6jhbzkTzra83uW7mx0`5s*t|+2#-6v2ll$wg$pAnNY^S&39sYnr4Y7SH4HuVO3c$im9ZZ>1hCn'
    'NKYHmu_iLENO+I@Xi!{$KFqm?DO6PhU&MMxU~j9d%%A!Nbun8=!J;{{%>A7P|EuztFfcAmO>tLGy{og4j`svW6iczu0kqM(hT^W4'
    'MrD3WUJ3=gzV0LApMP6CC6Q5Ec+_&n7xKj<cCyis!P0=Aj8ixYb+Mi&HL-z$`5g9W)K`l^n`2}!t4Izp<erwuDluvU<AINur=y&5'
    'I7&Ry)peL*6e@Z+Im)cHK8CHJDBV)U4Wlku$c9Al%9)^VBz$w5J4RMo+sMV&85ABRLCQE!u?v86ypr1oYHKohKEOlsa$3d>_R{PX'
    'TR3*7kj4US<+#;8)E=gPwi}G5ghPA4GVX!Nh{F(d!~i7cXXnqj#zOI-Z8HdUoG;*JV0gBvsOzL+*brIXydodADh49M%6+A9*C>V$'
    '0z7}JD~nkrx(ygN1STN6nXU|AU}!Oqf6#Iu`SU+B93T+*3_6EUi6Ooav*NHZjM0oMt#MZ+UNI*)D$L-7W=10fr9Rp)H_ll13t(oO'
    '`Lyq$t_eKTp|&JO$_h*|d}}1Z-Dm7H9ydh-iIKi!dI~=l7rEC#t;b8;Fe{i1;{yp!<^XZ?ov$YB$JB{lf^PD=V&-S|X3_VTZ6g>R'
    'C^HdAc4?^F1(ovjT?RQcdBhi56f-rcxMLDIrfurvtoFtlf)j8XtDEIGtJC<SAUavq)g8Qt`EKY)j;N)n(K;&C&{o{4!73BG^Sfo#'
    'e+#{vidkq)s%vrDNyLoDAbc+2r7vU3QJ}|`ryS$`WNU9$@8#8eE|JbI%xEgitG({$Sg>;ZKCTu^vO?ZnkDM3C&11j+pb$1&oWLhq'
    '_NaL9U^%((h1Tq=JZTNj_JY0f{>(1NOv3F-nmVV0QZJI-;@b2bRF~@#wBrgMWsKf%;+J}2BN&`;uO*BYb5NEh&-=lxpP_xS9_iia'
    '$8N@))=0HiUDQR6)PSR(V}a$ge_flzQ~Vr+zZ)UZ+}Y0a??MO&qz&>z^Yx#BIUnmULwIG%lqoI#H>pPG%qyvJy9nD<BAR1zmypGU'
    'r0t{B&CRCEVX$eEelPk{vrO8*CqJ>u={@|ni3n9t^S63z=hV?Z@WMIuk}l(58DVc|3yUVsa6!;dBN5-l^F63H4#(_$d3aPiml3B8'
    'm2=AaUT520J~EWIwejwDpxXaW*SW`BtNiagbgFEQOTRRP$n~!w7H|iqMUOb4qXT8Rw4Z~?&o~)0kc`C^&)3qB>X>kXRep@ixIElw'
    'n}rc*)485QYEMnJqd+!|0Ah47GYo@jiG%JM266JO0!4}1;-GtmK{E}5>WG8xb13}`<Oj;{b-7)vZjW%AIB2$EP(ABGAM^4p9`v#}'
    '=z(Dn7sRFcP1RQf+fIaG&^*JS2I8PdZctx?*Uo;?`3(+=vWtTj7zT0S7a@j0P^GcZFsQLO=%HcIB1JTTasEjmDytvO4TAFZ68YZp'
    '?6CIY6UWml-*z;v^S5-0bMH+-I>KgYtQF;V15&YFE3LeOoa?5re-lYgwW*euaq;j+nlmjT!V`&D;l8{Wg17lf-b`i34_cp9_}sx$'
    '&<wu<GD5rvI6cpNY~jHqA4_z2(OlvT<w_(r{AoY(VAR7HcorK^bL+yhu0h!YnCBx$7>Qurz^Y2Wz(1C9`bDh0S|w<Q@WUfVL#!mF'
    'pJFEdy_M`RR(FD}?8s-}m=OF+o<Y-Uo)T=llK`UuJ1GDs6O$Z!kdr?<g}9?pGZV8ku<01=W%O>8Tw;|i($Eu=={(jzMLZZM2%*iy'
    'UaIMSKEOXn9LA6M_lNLD9l?^hAOF@UV1R?yMqR*?dm#JiiP0<u{XEZoh7?|pHkUI`U|*$b{L-{xO*j(Ku_gMRombW)v*9;_-p%)c'
    '{*Aoi5jW+pn{9NC2^$93%{>ck-r`Clw0WnoJKMGZX+$D`5vH~-k$RMY(R0h^-Ho?W9Es;wwlVS6@En=U2b{AS^h;tix^4+t=>#S~'
    'TMrUuVg$bUyUt4qK>z7%<N^<@q|utx6e+M102$l61)h)s+wJ}k240;odmtqTm;?M50{t+71jD&~UvcW%y_e$|$EnEE+m?>!b@oDY'
    '2dI?lIA!bE=p;vK^o?I8x8S&%M)CZR=;@57J$Acu#L<A2s8&4iyN2GXL^%QbJ!N%dfy7Uz8HQ$7Vt}Ou`!J1LY(rh*p*TVuOUhB;'
    'HiPv845vUwb3YLSaj0;!u(0~PxMKAC!fh~n@QUqo;l$+HBBQO!V6w%2(gIP&G}##{0TLzoAF{tX+-PXl|0?#8J1vV5dI!PMt4d(L'
    'VN%y7)V=~n8zX5goE#&<wF*YgR~NoCokaFP87!B!S5l?1JidptHCsmp^V0Mr7m7=dRc+~P3zWf-JKrqnfozA~99ey&$FU7Erb%ze'
    '&vD3?M%OS`b2(>xEVkM#gC;g@7U%ubfGV5Nboh#c=kFyrlA^BuG^GV+K>93;9}+hw*syidV<=Kw8xH7LQBD0euMo~W^DP#L7qKVV'
    'WAXWQAobkJ8_Tnr5UA(OA;Q6Z9jH63y+$6Y6b0()tfGLGWmL)&c13r%2qZw6+kRde6fOalA;1z6Ah8%n$rjWC44f^2g<uELWXZnB'
    'OS~X^@%;hCtGAtswTKQOaG@;oK@ZnbOn`~=jIQ_0$hfs)lvbY6Q<rSHM68K_RF}L-kuUMNlG;%=35}AmFH&t8lz4SsmXSv9$3`C?'
    'y?u*;%Vj{~hkaQF>~0cYOZa3YLBSudcH-PqsRL62Vk}a)eML^tYgn)Kvh38^f;GpZSe~AkHQvV}<_<wqq?u;(;+Ia)DPrMx&MEe5'
    'R!38eIA$O6r0QkIhPE*NtK4VA_WXMQCv-bw?k7{%@@c-pT+)`jhVdW@YTAGHPbb3SQ?t__-P}K;lZF5KKxyDIYQ>W*fV+S>@O@wo'
    '42`n@ZUW}OcEB8%N0lU#&4B9J<D6sygo(2jb(RDD)q^)YS6?}Bj^-aXL<+2vtr-nQ%7EUgVEQ;zkFhT)o_27(jh6r`X8^EAkpt}~'
    ')z>d+0vt}A=#0S9s$6=~ZUX#GJxQ>MzyR#cxJZe>!s^z!=3@f<S^XGPr78eBbJ3bS5c+R2?p!<&dUD2`r;T{&Up;^RAoV$yw8zxn'
    '=<fuIZM?-s`X2zEki2BzKN&c;z0f=u;CrTo^8XNU=HL~7gvDh&jkvO9d~*+(+)lGEOvxnzQ^Vt(G`vJVsShM4AMFn<o4MN)HZ?;U'
    'eoj=o$<io4q6q$8s`MivNiw;{7HRY`*4qxF$D(MU(8X|rgre*Dg*KXHKk9bkLw_f;8t(N1FT0TCO;!k!@o%gv=zN~t@=9QXgr@WP'
    'rLfWhrxKaKr6RPSWliPU=|!i?wv4qMU>(7s{uR~5;oXva&+S-w(t~{8h$tekWKJN8mG;@f5=vdexV;9v+<W?_V>ceBI5J~z9iIJ8'
    'UfHDP?zQe(oFnz|mAwmkRucGtxykI`e#pX_<6|M6tWO5k13l>F=AKG$_lrER9eU!6C`#Y+R~A?f>2)*9GrAMbjLKREYcfE>(b8x$'
    '&lDYqv(Ye_Ko3(O@swvGgvW%DG@^@n?*@MT<JZsfk^phcDYzk<?;ggSu*P+|&}vsnL&34R3=AyNZ`0K$S+UnQ_SOBcV@MR7zFd;0'
    'lTfc@*}-}SJE+qE346a?@C#Xhmo<Bao$BZ{(WVNP+i>&%8QFp7H?uTqk|IP-Tw{$+5rX=P&@e4l@jT$8L&)EC1SmAzgW6)MkSDCj'
    '=o5&$a40KG6S0RRIm<<WP|H$P$b#h0`n?c^+I3OVu7C*<>z_^pcx0(;iGN||1(Ng^<x%hm<IJq>c-v%8&X@dC)?TK57!)S#e1RqM'
    'G)$s=lJ4AE4t=FGUB%D>iMopdl(H9$B6>6QvZ;}1)2DUgb!)41%Z+oZ!5^mZknOjV9glDPGK|er^|J|Ux9GWnBP@XF`7MC!tsbZW'
    '0cLdI_?=$VqXh!@8#S1HDR4M1x~UuQNgxICw09QcX|Obm*T)t}5pxbQZ7yRL7h9oJ6ZI|C8+yrMh11N`sYGQ~Tn;OmE<{SOP4hi7'
    'ajGj0{j<a58K;mH+9XK51YCk?`Q$(?XxJo+QK?KIy3goswU+rw4l9#oo_<1EtLdcVsc*_TfO(Rdb(C%yTX}~m|3rdt-j>2DYTG?Z'
    '{*^ZvB6S#Ztv1jh&s(vHi5L)D6{nEZiESuc_@?wLS49JdDdq-_)VwAO%cJ#-gLf0M67L@Vs+EUm<&Izjwg<Di_mVifLV5)DIQU&p'
    '##aba<GBG!{*Cw$3>MhvLmI<)iT6Hf&4nKI!M~dF3Ywyvni6S>?O0`&hG{w`t+6)t?0Ud^$ADng%Z6mn3}X&K1MoH*5ELT(*(m%Q'
    'aS}LzNjiR@EDm>}^i?n)Q#O;G1grzfD939RkHI(d!7=JIldWwjrp;x2s_kWnKT%imM#b0<_&v>rs-Nf5K-h<;@YxYR)|Vj;OV65E'
    'HmEk*PGF-Kzi5#nlO$Lm@>4(7!BO$W%H59;Gme?C&v-M$Lx0xzLToxDsPkP`v07H(YP8JW;rIt3F+s#<489`~9m%VCki%JB_IZdf'
    'L0_A2cPek<&8mpCM*fsH!!Z&mgha_bg+HzfNjFI5%&U|DGftFES(fo_fwlXT<siN8@cZgdyo^0rqqGBQ@4E_?N^GTwY-Ljd1|c_7'
    '-AB_t6?3Xd5AZ6@n#53~278>$DsgNV41i?@eS0Ay$&qmH)bc(C>X`4nug``jXU3gd{f?NAtH=Uo`Na<As8mb5Zjv!Wy`RaR*Bw1g'
    '`UiI94P;+AL4AwrVJk&%W<?Qx)^?Hg%d_9-B%4mW%NJ&p_wZ5&t~-IfcoA>uLA31H<GU1_Pl0$;;Z%EyEsgO{YXLadEJeZD7_#6x'
    'epj?!9Ar3k5&|8=pId0zyv43W*p@M`)|f16Pu{+)MRx`}1y$Tc)=Td);A7dxup-G6!S9VkcWdUrg7~8(Vb#DV%>LAs7JL0!^8tuN'
    'yOlT&-kUM>v-$hud9z{Qb{UsSq!9byhen{D=-jXC>PwHZ(!zh6-kb#P?US9Pt9V6)+|6K;4EP5x{_*WGcUZ_RmEp31#GMqo`(6o~'
    'EYTfd&);+|nHcsrBgHe)L6+{5R|<c7BF&_;j=(sJ%SpQqq?WBxXi4jt$yDGWY*fmH{4<?;1|YZ+?v1WsQ|zxIDb~R_?BHdR5{`FC'
    '6r1CT4?c*S!g~``{Alj3i!mwLsZqxlcJMax;47mt@6OD_GM>ow{#ri6^e|THBII^y^iS5Ik5I@0OLMIk811rXHC|!)^1{p2=bB-j'
    'ZS&vI3NDMxyfc;kT%{4Kc9G#-$$YK-ug-meB@Z&g7qHoGiX&F}9+RtJr$Kp@m*{!2=_yqSuxb}GEPAjo;$bnw&D>#=V23V_$h<!<'
    '-@j%__<eRcE$PI^jBA`1rj-W*3`#;K@xUTFt5j1kg?7=j9=fee4|f?wCZEaKSpU4y@5*bdA-xq6Ut%~3ZHR&9dqSS?aUM~Bk<EH2'
    '+2LX9WJBy5LB(t;E2wJEw2!k?Kpj_0egdz4QN`W4w!ibE71-n5t9-o(L00_mCIIFLUcK&cN3PI(`XMIExn1fr<~s=OuIvpj$-w@@'
    '(5}r~BTX_HI2uV4X^Trpb^7Db37a%innOG9BxKb{m@M5^`KBPw^3fQnr$gurq(FS|iJz3@%|V=PSZ{CXyo90y?((~4NePjT^c(Y>'
    'g`w!Iyxh$crN{zwlUqH#Oeynh^qAp;O!Euo$1fT^D$ooicnXrz<0hKvB9x$sh;e&5J=6>(*QZ#mI=`qHO29}Y3}mb*V@g<tprggH'
    'zLFV=&j3VVom*;{p?LSPT-DmX=yA&$LETyJU9(0|_hy$L|96OXQF9lB>wg!5Ezq?2EB}YuKjB;0LrhzclGFZ^Enr_GYlJ|RMR>&p'
    '0su!|cYy%FiPokV?QkUCnRYfal-DrpeZG?^N(0P3U+!v}F}KDRB#U0}ZhE*?T8GrrVIO&#p_Il+H}CfGHa#Ne;`48SX{z{;FVW!^'
    'ImFKlCC@l?az&3Y&F=3%G}7D{j@cD02XVCNUl<a>sjS7(V-YVDJ66iB<ohDg>JbagLfXs-IX6>s31T+x_m@sn`87ysdZ)LP(Wtr+'
    'vEDa7lzytZ*j{~A&I>ieVUQO)OP5P4EH<3$V6$4)C)-*s`(rIE_r>8?E%)aBM*j*L<I`Zk;=Pw*k{!vBSGJ6A%7>)$`D?-5vCN*r'
    '{(C8pDALvH958AG<ku?C!K&r>$}EtW!QaFJ+C5(#7)KvsjgYBsJey_nWlo)_0d*<QPSmsIDUfmYKEu0Nys>Bzvww(iF15dH6g(-o'
    '_M=hQ)EmiVEG;r|i#Lw(v<Od8mW&lAPQ^dT)-Xx`D_O|?JJ>L7p2zJ#>=<{2<np;YuA*VB;T42oU+L>)kAdB%k#ol+Tk<81bw4tu'
    'oK)1z1Va5iwp|25<wv$b`&Cyn;Aj)?CS-;H7WJ8msIsT+KY!Lw3CoCDURX}%QI(-b6=Xn3?QOlq8`M$E65vzX2ra>4B)zA!WJMmN'
    'Ux|?$@B^pa&V0DCs5?_q;;qlOpSu&6mGR`>iA@vQ<Z)w2h0iVuOsnI_$1e1&uOFef@%Q5O<lA3b1UtNnG~8)hM>Y$FYr&qc>1X>8'
    'ZxY$YOw>gg1WxwkpQq$PjT>>weM}l_nw0C3;F}WY5oGB#Izy72{iXEa^<FB?zNjd}AoumCxyi%ZG*eTy=p&+8ZKBMJT=;6t<3;`u'
    'Z|SfeL^2$6IpSZ01U;jc<(J$61P>q&jnEIY{{EU_#mQ)TM;Maw%H}bJ&&gW~{?6n}kd)}T^uW#dwCwc6`={{{wuiUkuMs22yx!-^'
    '58^XuDwip>7$k|QOjuv5oBW!`zHr0XBqAtjhi=UB(^li@IU|Q)BVrn6<KAcE^Zb(mn_(yf@?CeeIJ&Wn%dvue^oW=2TTC7bMac`d'
    'WNb<8dK;fBq%*5-S;uB}@H(P<8YqwWY!M$(Q>uDcC9ub)7G8J@t+vv5GKgA#0^_Zqoj9rZg==Or;mzFy_tllmSLn`qLTS(E#3@i0'
    'a#7H@R!M#4nXoRq3FqK_ns+kvhU_-U)U!)ZvVpC<*jdUqlPAlsu(6h>8J~+(##e(RhKaW^6O~PllbgEN6n4w3!E6LQV9ox3)yhZf'
    '8EL=ZW_mO4#sVv<Wl&9SvYu!J;W_amMeq#JA?{#*tUHJtXFY?8VarN@eydYD)zjD?lqD8<COMI;ft@XGW3qe~fCtR(*UnlLl!_fK'
    '&_|xb+KTO}_>x#v<O|U!!mc_R)p-{Of@-C!{eDuvFBb_uLH~=GeTuGMt|z4cS3MNJF1OXKRFWerTD8_>Z|1uqKA7-kk=N7IIhiTQ'
    'zk%s`QWtvSfkXLsF@NH>+H$rPg$0zxK2c9c+o`t!NdHl$fY4kplF^A>@axFT=>5YrE%EyoQj+ffF~6%^Q{)}Rta|sG78{XV<QYf#'
    'YCQL^&&tWYVs7`hYSS!S`ZS}|F<Bue8<Hqy$h93Ii?jKf==9alu+tJ_QP4P*U|yG7k!&-uS*9l6U4PkAm}k(`67c$6v=qYTbgLZf'
    'sn~N@cw^*7Z84r}V8!uHh}Bn~?mhkI+b%wdU%$gb>DC8J>$>v|g5UXa`_-tV?9{mHdzbWd(~?HKb%+y?c_Yp^ChnjNgPcY%GhEnq'
    '`|9uLf{FQqiC?fpd;#8;pjuX0{8ByYspa)6D|1FT0AIXJlb2Xj+-j}~<izh1Sm<BYYgweIm3M<FVy+ZzZYolT08=rcrz%3{*Qq*J'
    'WrJ@=F#9)>O08zfM#7~QrJi!-<d~Dy^TL;&Z00#S6q~x4R-(&3)K}ML#<${>U3uvjm1=|6GJk@U9g_Nj2P83?jm|V)CQwe`setE4'
    'D-(Ta#5~A}rX;SPD+PeLWpxe*OE#Xfq==~=n^}yC!GomJG%8-g%xoE90%9X`vxks2VwE{2ucq)<spi_ET%+6RiJzz)5i~#4gOJx?'
    '>{Cy7Q6qYZs$G~)SY2|iI2*)u4`efk<)>nfPHi|{&rJUH8<b}fzAxkDN;Pv|N;jb31FMBIRJNj!B#PTN!KBFQkJL2`^E<HE+&CGg'
    'UQr%O)4AF&hTO*GZ^ph=k)6?i`h6DCRKOr|@msmsTJ!8u93g)GG45mf8W)c<<?(}aTjzej7R~iFUu)p@X#Mag*Lv8pV`hj6Y&|1A'
    'A;>wnAS=8w{w_uACqp|y9))I9$au*DP4OdM*=#JS5sjvJVoPmH&?prExvkKu0wH&d9F3k5Ajk@hI-EsXK3f;bzL%hpY?;{=t<Z84'
    'W@xI_SMVlf<~DhnqWP8SiG6k*Q$3`go@;6A1x`qc_Hb&a0&bweb$oWPzv+4_TCx7e8wsx$+u3s7ijd%BCexP$P4PMkgxE(Zno@z#'
    'wA7+jXf!68k}x^iBpO^{iPoLYvn5(vI)AyW&}brQ;BSRS%12UXa5>sk(tF$zjfBe604XV2D2btPl(s@!N;;QVeXPFZTU`n;E~J9F'
    'HO);>YZCJcE+A!nxwa!$o#xhJda^E9WXuk5NmN1n$}+BK?}J@mwUU@TJ$(Xl2j?$Xv_zQ~Dpn{K<YCE$=Y4DPPiLZ@W@bH&4m+}8'
    'cAxrkt~H?75r>iRf7?f_bnH8ljRj(d2$6C%u2RxAw_RBu#UtdUUaJ$uAaS*IBt=%EKV;s-?}K~d;^<5i=121j&$NaYMM#JSIBjs*'
    'X+z_Nw3jBvu%zNL>E$XXp%`M=DOGSVM)Uk6Y$s8s(+^|vn2!ZkiKlikC&EojDaP(er;X-~$#mtbG}sueVA9qBgVVZ6y8x_071&0L'
    '-u8B7s^S<at5(d?#Kg986tk%dO#KXR;sUcY#cb^Ylg7hamB&WkHPhW$(#6~ft}toUT9<Btqs3qs)Akaj2Dx0J(v>XD<x-U?%ubVq'
    'Nz0UXVw|z_kT{o2nW=9qtIr^5LZzu#*06rsb}Bndd@qi230aDeu+RvjN%av`i)*bi$s-mfkX73NQT!@TEb2*vm=nO(;<z#HIGCz~'
    'qP}_+lEz%6J1@q=+lxA;^E$!KNMKSxM;Po~wpTYiHDqi%FtMK0O~$*~m>*6=BxPkLJh-~=>oIRvV6cqmiX%Dp%KoJTYl|nB!}PFB'
    '{FXNtmToy@>F;L9e~Na|q6}wPv0?j959;0~oASsp$;p#z64f|dD`|<TC<SS%p<4y4F_m2O;rH9DF_mBv9}N1tz|^yg#ss>+^tf;Q'
    'qjF4|E1x+kOfYNHSuN%Q(}Si%>EQyCrta6XwU}Y9rIrR)n3D~<88b{0NT`QUnqksl5*i0=hN<Uv_H%*RjbeJcd-rTt&q-B%39c|l'
    '7}PChn9~e;Au~*>(wgN8lU8u=<_hznA!f@2vm{^xO06)dR5QpGCaHT7pT`B}i-ddq)Wt5g5%;Z&-YzhST$oVNn%d+c@wrbLODWjp'
    's>O2q*aM2UUO<l0o4VqqbnD?OPMA^J^w|OKP;U@5t(a>%pKxj8=vs1%jE9$xUqJ4l;E>QlMG6JWoJ2i=i`MB`(3G;RhnlOo09UwM'
    'P&*VYUaCx`>W$ibFwF!_SiRm3x6mMu=MLH~_s|x&hc?hXv>F>W)O7>RM62`cX!&c^@^%C5D`P%L8QMX&(4d>A8)y}Q1sdP}CbSEc'
    'N$UXIdIhg^_vY=iduU7DL#s7rOrHPT3VBAf*~|L7fu<77jc%ZIre-xuwE2wL!~*RMQx4i3%|D9?m^Vjj#_HZh!lkwnWh>Qe(!Sqr'
    'BB7OSBdECyt(`kW6&VZNK&#^h+6K2!Tv6~1@<}LOs{Bi}8nx{5$rA~RFr6n|qkQKY<#X34@4H5+?;0i4HOjMXs=o}S#QF2@x<Gl0'
    'Q2>~rOmdB~)iug(GZe1<l_>h|eBk<Ve|3#A%{59_*C>@7j=}$w_3}?e32ruM*-0uu{<eDJhs{da49+KpR`8ioL~UgEIXf>rN^&?-'
    '<8J-2aeDVErh#xJr(8FxT7DTKbJi*QeYRZh4<f|u#2#abekDRv{d*Ox^5H6?&srqd--*fR;RlR1$ky!pOe1nI@wopzM7U#xT_UpY'
    'ag2LP5^?sufV{-q44`=}u*k1a%erhr-{Fw$=dFwZFuCp`iCs==4}h7(7IAF8rDIc>vicO|&2rZ&z^WY1yT;YCWqj)fGWj61TB22p'
    'b?G@Jb6x1<8d(oIe%&>4S+`9EtntOAwSY5Mw04c0$HZokE^b}u>~2q&n+>GMG|{i%&s6cPF{>%%O5HZGO+JniZ8V=&x@<l+I_sDt'
    '7bZqnM}TW&-2<_!8^|QzoiP=(1ldju6d8qGBkLX`>)k-sRbLI=Kn@_Y|DdpIWF;T5wcaZ08d=FpbXG}&y<8$I9uw23b)h-5E_ju0'
    'H~o?+l_<4IKN~XQli9R>=LZ{?c8O`XjY_4{i@OyvGv0l?Xn$Btn&auiuv1&+3~67%!&(P~I9^GSs|wGAtdwgzYBd#vQg+Yn+XT5p'
    '<!R7s)(&dUyu5B)#}_@US%V!Cl9Gd*gZ!UGHf?_|@;TlqwdnqwFPMY;Uq^ni!<aQXG2b=6e{*E6&DXT=9F~}W*14MJUwEbj8avl2'
    'idnbvLc7sxNVyY`v~y0M#xyRovcdA1)1A}(ujsZ_?l^YsIeppB>-TD?`6e;jJGdE(P7HJt7}B`+%<VLp^r3mZ>WQ*6m84`|NIAe9'
    ';6DHuYyr%+TL5X~M70qk@`%7AjJ3EKxxOHVo(*L76UnsPm;o-sm$|b=AB}<fEqVdbtxW|cq6mvpIQ9QZ&U_7SeOSz^U>_W}b=Zdo'
    'vTcdCVg}sL$GU}nFmLC%u$YXrs7sp%RdVHqKyvBRho?{ZOvt=JD{0$Ty&6*$pMSGaTcM<#wsTJJMtNQGLq0ITCa!^7s_Z;4=;}^+'
    'xAfjcpnmpD0k@Rom7oLK&H%SG>J6aF`ASc>)bDRWZN)_QboKqzrIyvhJ;grsf-@-wE+TuvIyO<&-7*;jz|w42OSolU$PaZwf8=$`'
    '7*SeNWL?YU4suOg0bz?9$ZsS`qV-IWyX)?yj#phEr?85m*kUfUu>hn}HXWSuae@4(PJ8{YFSka%R!UK3=tFy2A>V_a!sDQ>x2omx'
    'a~FuD*!M$RE~Ezf1n%>2xkQ<ez-g}6^9CLJEtklFG?oKAbxjH?(lr9E2D;p^@8}Qmqia&Y2vQ?lBJ1H=z|qVlMJgPvub84PX<buY'
    '&3VGxB^4d5KQ=n&ILC^Vy-S9@SxMK${-k3cp4KkZ(^A=zo6E?v!5UeqlETTR5=XrCk|pmZTIp6pm+B|fuZu^%T|4OcjjK6mIcPa('
    '{|&UtW5yJ518uRMThj{do*n{ifmT@$TeU(Ptta8MLOa5Anxo})FbuajS~s9eClWNfS3v$!wOS84Ln7Z?JI#HpxaAGk-aWK>Ml`21'
    'H%Jd*V2I(bFOUtpU>GJk*FBZwJ#5a5IJJC4+wwLe7dON>>{kX{%Y^y6Z4gx}INcaVv%1l?3|I`Kwu;|`QTbBUH$HAQYygd{5rW-e'
    '0ls;=&4ztUGr;hvJ-nh+=B1SRupkmilgcIdfvNR2E9S#!*=0VU6)M{5TMa8uCi(#*jx|Hu!D1LKX~Pyqg{8ILu^#q1f$6nbVKLo%'
    '9@fK@D+E}ZAy!&WEX!eiMeZgqtR9=&)i6I2)|ZLR)-d~tmPx>Jm>xERqTRhB)K6W~^{^tupC?9>d|(|nl$*<Xn9lNl2!EXcqz<c#'
    'VfEPfug3bfa4}4wK_iV3N88E0VKmjn7Nv~(sqcEYH_Y<^;q*%^U?_{LVR{ty3RP-(lFQv;!Kn=8ps`FYhoPdnsAUy*e^@1><FY%$'
    'NP<AX=G}2)SSx~ZRC$(RHe6niEl20ZFcOx_l67~61)#*itXGLU!%&*c#K31ARvbz}TyiqQFmm$W-T1|Ob;u1itDl-EGzz`)@!Vf&'
    'RPCQ@Mz>RsMg9<;gi#wZQOf6yhkl63Fy*xV64GG`Tbh@5`|2eGlyI2Y%`GsCy*_9m&D{ZFn4C|3)!!Mn7U~7htsL17M+GzaE{+OX'
    'y*9kK%4Wux?KY;M(XhfyEb9U@Tz6mcwZ@!6W9zv>jxx+Vw*W_r%`ug#l+dKUWQ|E{b^>rSw>2iJw9V^WOfdb<8@M$SOr>lh!OVQw'
    '8dJ~d2_A%4V=A*L>K?l_rsolUH<)88g=rqQ?ANU^l~<_Sb8Jy-Oj2SQ9+6(wm^Piwoo9`y1nXrfJ6dBZwP{%UlcCm_N`LxC(_COe'
    'XKAS_$%q+n)m=<hN9Y2R)){t<sWY`MF}+W@i>Z`|a~D%->2w#9<ePK@)4rd@EcV8bWiWR@)Rt)<))%#Fp^*$`gu#Nuwgy@5Vrr>4'
    'no1tbR=xj<12^JRv(w^l9$Yz~rbRN<YKx<VgD86OOLEjI`qoGdr)dJfc1gK4`*^G%PyMzvoQhn{mSGZ<F-m+G-_1mB*Gv5sA&#&='
    '@X@4p;tH_OQ??Pda^fdp;&1UE!}qjA7hjLil2*dg)g;u2G0G7y=PQQyCKZd%(wBT)D$VgiKed^XnE+J{$TT|*3FHqXB;~2ZJWMpt'
    'PAvAkDPbFF+a#QLv&<J9lXC)lZ%|oWX4&gaBVC2%EQ=jzP0uLpg*>Qg`)vtw13uuU0R1U51XiI?&Gc7_{%j^eegSaa;Ck$UtkjSG'
    'r!*d{JOHBooM~mam`hq1UY@U2|5MtD9ZY|=k|67u4^bY?G<j44YK;N!bU>{X{UyllsU-ycrkvCl5@dRGokYLKTLqy|Ti#Oio8}Ha'
    'B|+XM#F2QAD3mlw5;n5RGKfC}De(=A8KO%X0w>C6o4(-yV;IRdxaW?6#FAr-sViPM-eg5LA$CfZl)f!DM+TBw?1K$DEX@Imoe&%O'
    'Tw;Nc(fBw#$&g&Kljj*;r7h;kQdTvGoVIs^#h92UeI)r-Aq%K+H2!8R(Mmbjo0!rIe|AGSfWl{%wNQ_j>$zy(^|&-=dP3Nt<^9B?'
    '%BYmhN{PC-V-Ay1)m(3Tbu4kiu?SI48fi1?Fs~FXTBb&auc!@qgO33P$76U=)zVL9D2lS2^mH>tDM(aJ;WjfAJ&9#qQ<Pb}qDzL-'
    'U!eFB6q?_1w<!u$9vw7Ap{K=WQ<O2htyYFYL!tVbqL6?`P}&To39DI?qIjJX39^V1y3hPetLvpyjjk)G$@hq#R4vY!4Hg9`mMEE<'
    '8<;8ARl4%%*1<XN=9in9&bzim<)HliC|rng+JQBbdNeC7aC)-%<C4#ek|Q}hv*a)}M{@XQN)EPXksJy<i{w!4StN%B&n!7qa8q(<'
    '$}z1jB!`;MA~}?Q7Re$1Ge{2c==T=4BnNE4`qVAS;cN7}u3M4=wtUzhxg$B`64@gQ$$|PQl*w`}Iq0-trAx_y*>Rz<t|SN6q)nVE'
    '%_N7BT=xh|$zg@?ctb5Dhn0p`X=x@oB=?eht9(+)A$vm^6UkxHP4Q@pu_`E7zSq*<ZpJg^Y)30D+lRW9rG;y3-D@GCqDy3NUBC!0'
    '?h?D8Ztl2O-X-=+iMk!7t4r*cnZ)5|$MziZrX}`^d}5M$)_>c7dNQzZe>FJ%e6-<md{)}SV=Mbtk;`h?=?QmF{P;zuf-WUL=B0-7'
    '2f1Yiswbm8%s90xFjBT$^|vO`0;7k6Trzd-h?e@8w@d!-HPSc1HLFN=-P2qyQK|PtSC^=@fJ|i|MJ*yS7UrnANat~vsQCmz(E^p8'
    'p<7*|z9v0=q^M)1=cN>tIJ3lhxk9BJ+o!HRY<FT-yyRnn>Kpp<5E^p&pt#8*G_*qn757jtbTOA#_%_N)w9z(9OTr<?6mlsAQB~c3'
    'yDL<`oANo8&1*yQ2wC-AiedB-?ghC*)gNKAOW}?_0_VCQUjy_J(ki<`)gR%CzpF*4Kf(%^OPf9dSAkcGsy{+vDOcjH{s<>LC1URG'
    'd3~FN7$4!{^8WSxB(m(!#z%mymlZ1W2tcp93eUAq)||PYkd^V|!P%XQhqmU!_3XXQiGMMcsgPKazCyZFV(F}`1;9Cf>Qcs2@hI4O'
    '?qeRFOVb-Z*0ay}ewxC<XBm0@;SAh2#mM~DV&H8g=d{NY9sUKY03>av4qq+{D;TZAkrbH3Z|;z$O@nw&_o!J3ZYpgzcg2Gp?kI~W'
    'D!{myCaiqbNH`91-z{RQ$WPW4m2JC(Cs}A%PJeJkuswGg*_6rbb9gP1#A$F3+S-`zjc1lTdtMSBQ!K>YU^QPB;DC`E>$08Ue}RmV'
    '%s(Q+$_p4WuA@^W5!`I65ySfDR;^`F{WoPjwWE0kg85{7F+AP?N0r0A$8cl8#nFuWp9+6hgrh2_?Ff9n^!|=K1TK1>Yt^@j!yi<G'
    'ea?wKHccJlctMAQ-<gjUu!=jjuo~^mgxXLG>{WeyIM0ARWZb#$#b6=xsjdhqHek0{4kBh2&l1=xy+7^yV|QXwvY$p={(1ZxIwx8X'
    'xY5r41!$|fzf!qau%EYwUgq$Rz`)$Wp~WiHZQbt#LDRo%HHju_6hZU1M0*#bG3!W%)&!$nv_>m~(RNy+`Czma)@aIO6)n%&wH;ib'
    'eYtkBsDQOn&E=rwpyi<bm(e`Szwz<(jWkLpdEbgpyS*H0K&vOCl4qV7&6vt)mS{G`hr0WiK~4HEp>pQq%~L;knQ(CdwYpAN2bq>5'
    '^LxJ>z#Z#GaR@PSWep5K4rUH!4(8v2*+8l+(;9S7FD4;tzZo!xajce-U$D}#><SY#inttXqBA6Y{uO|m?C%|%VT=``;swP;AG4Q#'
    'Pc&fVAq=vE*Z%~l1T3DHOKAnF`)sZY&mYvD@%&x<s8jVr-F8?UdVSm%McoRqy5u;tMyOZr(p|oRB1DqWU|#u#jLav<aw7XLF(RHc'
    'vF=w|^n}AZ*2%m$ssAfuf4*@4i6i08nKivD@USl84LLZY>u=~jrr&E*PU+IY;-1yHM|<JjIWVL%_PbB&K{cyS48i=|#BTgPvj(wa'
    'g0~U#GyrilZlowN-5DiCZ9C}2hxJ<H#@ObiyhyE^OKXc0{6rAWX(-1!$<|~QaC-gp3?ZA3Dlt9c)X+5cQOF=&#b}427S%}ZFDwEe'
    'yA+RE+#xd%`y~LdOPmerDtb&HO6^3<W^|%zaIO*&#wAL1AZv8J9gx;FrNkkf`aR88_rD|ymw&vdNcN3q6^2Zs_FxiZ3q9YYhQU(V'
    'g3Ia=0Pe`M{ZkY5??{&jOfuNBk=s?Vf;6*$$sWGSx?=b|mSqMPZSSeUC}g#n8D>Btqx3&)S$|YlqI*EMh@s|~WvKS<Ep>L&f-U%M'
    '>P2)U)<t6bH(0t;-wM;lklTyaw#h*{W`AqUTvQ*EoZE%La{<9z?#eX!f|GUYuxvQ|@w97;HFllp=^E3fMaCt%QK$grJ6h-lqLK#&'
    '8%b(fR2I*Ud**+m7K>N#`A2%x`D6nP=?hykvXzBV-m`MYPrrc^@?_nB8k*{Fl_6}8wBtraD-80RYcNfw32OxsHZYU_2oG7ifCqKJ'
    '6H=vV@?8vf=)nr0k3EbU?fu+9pE!fbM^m*jir)HE!_DQt?<V<kXZV0m8;zG6CehA2OY2>Q)TN%vuC(dYlFxLOlPJnz`0F<IuUD0^'
    'AN0I?s5=8f|G<yrBviK<dp$Bnvihj3Og8UZ`x(uLLAyHYD{U7`rG7Uvvepwevo_@=n9n!d$k3ohc3uhA&_$Go(D%8FgsVqtV^5t2'
    'rbZKd3d2D6OXAutLT}L$t;h(KF)2tD)@_NBRuVpUh|lQIM$@NHrLLh`=kG$`x8Ti?96*lGSC!JVP6Z5chWTS27`JV{OxCf!u!?kB'
    '-Msr)J_*J&F19**epOJg1>_ZI1&e!jt)iH;!Z~%0&&sdZ)alPE#4V&2iif)C61`-{2qi}YG%E2kzj(L6NOWnzY=%qyLo?5zvdd-3'
    '9Ay=pF79&LI?yFkH$!K^Xehy$ON@IQ-+ZZrahF+eR1Am)5+)J1wX9i-NHE^9OmAN|PWnAYK23LIHPY}H9Z4@wqdRe0q-oNlS!28;'
    'E82{GQ?%RxxXm;YPf<qVN&kJB)y{{=)i*3o*{?YMQe@F)Sd6TWak_K871_u%vxe-M34*wf0>Pv0RwE~BIE$p)$eK%fLFxkS8*k?Q'
    '%Cxgm|IztSM)$EEIYR1{{GyB%(A~5F?;XK)JtJmF^C2ts@a}!{`@f0~=CW-@tb`6qPqs|zs4tm3G)9R#Km7hwDW^ca+R@lQ=4e*F'
    'm96iM5|z;)AWK{tN~KcDbHZervV5o?P~`{S!iAy$cq-i?dvuzp9n(hum+FLRC8^?}BRNRToDyk;@rOZ3FxqRjZ0*PO{1PxN#Jzl`'
    'tECdPzjwN=vV1jM?gL{s3S;xWtRpV5UafU?2OMt~%sG|eE_k`X47f{B$GhVADYu*M(nFS3Qafh1My#)AV;yLTSTK@_<FoR)^;9_z'
    '=OqKfCTWn>o?4g+#@$U3yP^d|^Rqn8Z-NLDfocngp1D8B5rb}#1ynkP=eWe9;}?AaQC=@XCYesq<8c-HNg>#dZP2IhI9))M$)a`|'
    'q8Cc3#P<=Cb!HOHgyJh`Q&kF-#nxx@rt?3Y$NbiyP^d%Q`?%cB0|A?q3AH)okDl}77tkd!<F)^7;W#hdVbV`9u~FE%vF)k%yLZ(t'
    'lQz<2m9cwf_o|*$*{wB_ZK#D&SzGHFFeRB@u}fD;w(o@U44CCQOxUP1S>fM*{$5?YD(sayj9Ul&P!cwcYl8*7H}ybSK{4lXO%R@b'
    'lR4NCedc9$bX7`^B01H9&wa|alC}~^9X=tMJ}m5Wn#1G?69N(VND|2Lsmzi6Gnqlfmx`|$R4E#)Zv3nl47)>DeSgpLU^3E7E9N<|'
    'TBopjek9AZdUc(G%)ShmRc!p84{CyeDUakldvPjaoQFjAJ5AP*w<&-jaxbZ$?UvcG5J&~U`##DqCUIE$dcf=mR4kk_k2kdcNigG1'
    '0PC`kP1$AstL2HnlorXZVu@K!KV;UrIJhW{Npls~@uIo4U$h|QVE!vGJzjXd@3akcEvN2ZIqu#1(xSoDWOl&I&x<+6$|LXIUx$`7'
    'wnKw*h4T1%*#y-aldx}$LDsHK&#)W5EZRB~wwH~u9U~gNs2Nb#xgxaAELII_0u1x#(O4eci#qc-xmvPKrcVzLbf!Qm#&WtzN>c6y'
    'TJWOhfSE;Hs&gb^k<vyvH4tuLnefn)BwIzj(MTDv+5)Q*t#2C{WN}N%ZOVCA+-NRdgQb*h<!Kmew1qv%u7`kiu=ry`Db@xHtg`eV'
    'jmd9eMEPABRw1^*z}#6wZ>6ay8&|;MmIr`|ZM$&E0un1A_(hndr;I7I1ZAue3L9vUZj#++Dz*+_vPJd*rUKRv0F1+z#i&;CiJ|yN'
    'xNeD~!lF=ISwR(@yNK+@eks$2{5V3XIG0pX-}(7oc=@eCvv<T$d%o_E=SapagUxo0_3ZUr`9lZ0h32#ySr%d?V7oG_vt1cyzV1`g'
    'n;SUB$o}MX<#gqAA+^-$WxZ>78+Tepb=l^FB#h6@AEI(Dk-QWG19cl3ELeQVNq%)$1V8LIE?od@9~;8BLXE=?7(5>O37n6j6i}tN'
    '2mG*uhGG5P8Ft8E1{lD*OF?NoThCI3+hNwgNp&@R9^pdju>1V5-wneC8HN=$4m)Cy`v)^F&v=;A;3@!X6xA_kgn5H}5#z9928XX9'
    'hG9k3VRwy+fZ7Je<179oGY&g$Fp&;3*mR1k!|w3IP8j@1hNEFzP9LNqyJhUMm3?Q%{&=p7lYnx%a=LQ5*sd~fPu~~kYFkM*pQzXC'
    'VyS^BmgUOpYo=L_A<}Yb%<ndr0+I6tb6M^l0JpPsOM<a=hN6LbmZpZ7VVnZskxw&&^Qzt&As>T_5YJS%2g`o+H1%(T1xuj!iEk_b'
    'SEQQ9CFBVBlDfF?Enf=BSp;i;?3ZAS*QJjifGj_kkNVXk@W-wvO?mVYtMXRm<jf)>#$^D~=u~zynoKm4f}WJiD^eBU1eF7n*<Ruw'
    'o6j)%k`PgxUlp?NaE1Vw47EMmv6^$OP!HJ*(FwMykP~E@=pBYw44pFxP*0uYJUqr*oTYh?MC)R|3qUq;d$QkFSFa)Tc{t-a)lq8n'
    '3sQyO<h)8w`@h#lSc>K&{!*}Ch*k5`O{!P)6Qe9iP{eFuf1Im0o^?*>gOqa|rLLjnM|E(aDM8x}DR~sz7>BUGq3uPbW_JbCZlS}X'
    'B$Lx}+F#VXE4?-P>)q#XKT38yd2o1PE6zyySlC=qtiJ}*`bF&8bk=FK7pTD0`P!CfoM7<vNCb%m6kfx4p8;+nmwsttoJ%73fFk}W'
    's%aCQp_~!{wohd5Ok9LV{N=#PeHU#%b^XEPBx<^#z;~}nh!<vYh&NmI=^vKNy3GT>#Xol!H{O$2a&LJ{9_R=BYpCpLAM&AB9FS%s'
    '%P#@atY-caAPsoTD*<{s+29=UfiCfGcRY~zt43*_ZZBNnfF;RXM}0AD9u39@J6i-2#R+Zcy5&Dhi*)KuJ%h4;Dr*a)P^8z+H*$AG'
    'YI@|p2||<?Qz24TO&FCZv4AUquOGC8>u>zO4*$jle7Otw0vGU!ieI}q$0O69-Z}bZ6Ppn}>dOTEW1VhdfM@VoiF%80aAZ`wTGhHz'
    'yHsZZj%k;T#3@Aw$>+!O0w0xWm_L#M@0JNX4{-#lZZiLuIQxzfzLA?zBb=10+G_$QmB3G#z==EPRTDTdXFV{1_ao+I6ZlZhdB6xK'
    'Hurrd@L8NK)(HQOOFw6XAF-Z)dlDB8Vt`kn3sw%t?n4=c<?!4OdDkuhZeNGPn>_^h$(F?fY(Dj{`R`&u!}^A*3PPBF*R8=pEhlb&'
    'z#mo*-V=2I!A<(k{^?9aN_NuiW3!q{6f#~d79ERDOMi6p^e<n1SVwoU@*Et={plT4<#2|O=O@`5q#BM!xZB=S@v6N%n?edk;eCTS'
    'j8PPVla4uR=(03|v=U9^w#OK9zz`C-89_)Y%~*X3J`7t<j1JoIY<PK+WX~Aeb4DJPrnXp9gL}G}kAuxTj*}d2uNoi`roIH1OdYDX'
    'n!e9S&bypD2{9zz5UT8P*VJi)_~0HfKypV4;aYlYNY32vsP?BcW)FK2Q1<ba(`PLB;Ycj?oNWA1WXWhEf!rgx>SEVAvg^9>r#mi1'
    'q-4fk+dQti^n7B>)zV1m8rjxxC8+HIOSmrA{;$F(x`2;!0UsuVmmaj^N^Dlb-80_|n`eX<TkkY7;X1qp*)VC39TIpu%q(1LYFBK9'
    '-rOg^i(pTToB8DL|BJ921vrV!J!dk1bH%t60ZvwOT{*lM@x}0#!$~wtxXJe$Lj&gI@EHbQ6&}76|N6-UPN?NZ6Zk5_*W%%G4Rn}?'
    'le{G-P2hw*i8O(eB$(NLa=1U)&<#w!&+nphwg4w39WI%`^AJY%O_TjaLMOtJACTV<0^CLtDMa?KR_*O&RMx-#Zb?klHt`-c`XyHU'
    '+CK<qw#AG352`x%X}#cdcxvi{V_#I03qEfxIejlBHT>jE{!H>7!l)ijFjnP!IP*y~+K{Q#$PkQTx?<}np-ARSBT-o2>YRE5&d2!`'
    '?3x7`6<ZwZgY*-NcYw(X5|YX0|N4#z;_Ak2N1SOUhMJJ*2}+!uLl`9mvUiZ6?Q)E<3!VF4GHQ?*sn)YG!x8YUDZ>$Drn9Xv!x0$W'
    '7BL$o#1z1GjSUFn+OK9VWwe;d1OueK==rZ(*08@`lrgQzYSSB$bM%ohT#8VnxDJGAD~4UzeW*AWwRz6ex!?a0Px)-$P2z;olE}6W'
    'Tv_UKy_f(oTivm{uRY34jyUmkAJGl3?&QPwo@T}0-Ai2dlv;-j&cNN%4GzL@pjXT4SH623?hA_5Bl;KNzOjrqU3=VzLouQ?x)FYy'
    '<zQK+s*8kg8!8d(CrcdrXG;2JN&4mseF3c(2&sGn6=U|_KxKAvaxziuWNFTW0jBrJ>H8=373fGDhcEPNhC);O@?SR=_6_0t(yf%%'
    'xf+^+@_ZJTX_E0J@8^jCgy~Xeoe5j6MW;HR+&;Q)#Fvm+%OVGj?ZaD!B}mTcU_vaSb@zkA*hrfPOH1b~D@vKYLX0J@c9O2q1An|F'
    '6On$XxRc9<LRj5F3Oh46y>w$P=L1m(V?#1w>yZD_9$uyj!aozWUnJ-ZhcT1FN7|XCY~YD}NiOBjr@ThGIY${^;@J!m2GvS8o5Pbx'
    '%gm7r^Qgy2O-9TypDVA@C#(^Tr2)+K$kBKIKAx?+Oe&nv6`AbUdOVqnq<<+HL>^J8Zf4w_Jzurq1F=Hx%4=$AiitzO+!m*$H82TT'
    '>TL+1U=9E*H>`Tm%WNRiQld|<c@Hnz8qy;^=~JX?xhS`Y{;b`lS+*QHMv-hj>a~vk@SFEcnGVHsnEKIf?#6A;pUI51rvePc*us2>'
    'TsV(TKXnzuoKF`xR}@<eX4HZoOJaln#LQ7o9N@|60aEbdM1<vi4!DT0e<-(26l16@xK8Ii5Hpvx`J>uJf(w*sHgGHYN}IJ)-TMd0'
    '`zH=2j6}=d1Ud5l1lCihSobA+Z#+)P&U|wB=-N+o1p$*+R_doT%>`U3(=*NzPSQ&J`{A8kz&p8sLm|rV?G+c|Ganscza4?UqLf}l'
    'gE^Ag8{l2PWy6Ra4Me!MUUW0iMG=1c^Q!)eZ|_twossbV?-Te)Iox(vh%gf8Z?zzHi}23{v0a3Z5ya{o_`exm{6j)t*4Kwpm{&7m'
    'hYjmmNY{01?U2Ic<wSpSh!8)|?FK9l+uE<#@R=Ua>7!}I5}OECs5oqi@FbZ6`=Q^3$sfZ`?fzsJk|Lm3>7Px+!7?$rFppkw-Q)Cg'
    '-ToTi3X#4W=(&-8U(fmdAN*aR7n$E5-pE7MI(SJmVpGNOhKDznZkQ}o1kt>~l3Pg>&dF?!)Z50yE_NWXeaG|bmZQxqzgYkk-xi`@'
    'mPKb=?)!Io32{DmSPtpuH1;WZULCU~N$7*^P)^_fiM~%HeQc(a6S$8}YJ8Qmq@#xE{1bTU47{hgWtL-Em+{~l{BJn!Yl8Y9+Y}hi'
    '`Yot^hicWsB70;g>7(ri7BBU_v<1Xny4iQ<9wukSUf<ZSfZ{gK?wV<LgKKxm_U0fwCqhA1rzk_nPt^!%{_<P+HGzhcd%dfBnmt2x'
    'b@fJ<HGjy`(W+?ulKDf1-crT>`sQyDcm{xs*UewkYp*JTbTXd@+jo)}4;EoIkR&f<5Jm!tfX*OvM@K_+9utH&GI>Lih%lRm>N~1S'
    '5t#OeO^)z;bK=X@Q-+W++D=`ZVuK|J(6$gntWe9$rkW(V&aQ2O;7NX+wwrv-wt(|AlB@?}CyEO(L7-WoRw*vzJ|~JkE&M(qLEkmi'
    'bTHoZgumKFosCZH3@1Z`6)fviUMm@)i@Okk%}EL>>t!jhuI5MKx2^I(C;MB`6LIDI&iQTl?NNOYSugXN_%W3YG<9-OC5$5qB}L-p'
    '^VaeU3F-F_4aA<vp3P^Th{}vT{yE7$qRXlo-b#^~G^ND@sEH{!f%>N<VRJhp`?gukdW|L)37V0{{LaFZp?HrtX2-<o>Y_i@{%oes'
    '`U!ClC(Li;tN0J5Ba)Xk^H;pO&_o|E%J=*Pz?%l%A;0^|@q;o29`3&2)-TeObAnNqI8(1N!QUY`j1g1O4<`7V1$<&k*pP#tga5C?'
    '7j<p9+7Y?vP#efc`MgGA1TMdw->7@@XU$)Z7pcvkcyWljxIm6xRuh7$I~nQc*XKFixEZ}9x^YwbNOa>IJ<QRK=fHDx<Dza{GZufk'
    '_gZXb+>HYh>x*ff-#E>TxWKt^*|DKDGYT_JOBg8$pVM;#l!8C=CpN8@rIiNo#*aj_;~{vHzrp%&Ji-AkSQFzwLURfHR5&^6WiFP5'
    'C_hhgt_36&I!SD&X;nK2EW$R{Pn|fGk!ajCEI&g0M`sFp8%+tjU7*BYu|5lj_{bdUeRqJ>UriEd!g1E4LL8~(IUuQ!z7+1MrL4oT'
    '#x%*!e3q4(APAw~usY_p!l6UFid(}UMez?3h)km43bXthDZ286ji(_w^|Fzcq%3cC365iKLS*1rBJF>`ytPl5XrIMSle2x5{CG;3'
    'B8B#^vD3pHd>-(L8QQX3|B)ubey}&5@_SffX3W)HqfGL|`*i&J%%k+AJ4e5uNtl?}y#*tg6X_s!SZ!qDHv!VIAdsg8^$kc^-Mwzb'
    '*NDepW;4O9?tTF8h<L+?hm-nXUW613mcyyi;gkuy5CE(<s{yVMPu=%S;ADSHH-RtZT#$_L&p79BBYYU=+iZmQ=R6;caN?YO-vmC0'
    'V<n965uEd*5k7_E1dQ-i+(tLT_i|cpBOH4&WfzpgOY;Yj0ZtzO9h3EQ6MLa~%Hh~i+)-0lpNXHfDiiEg7Kbi6`-yI$T+8}Mv4Zca'
    'V00@z-fQuZu*X@6H}{X>YM2rD?<Oi-0{_zm{IU!9H5c&f{}p)d*NNO5_sOfq#H4ky<&kluHRR|0kh>N=&z7_2jb=OYby<BjJT)uf'
    '&dF`dKI=K}5kH~9U!@v9vJS6J-O`^pB=Ba~BzV7@N&<7$St`IoaCN5#*yj440N*G?!3l6ur-`r^BAlGGUzotd#ZWIEUVyw#J~_M%'
    'd2>Y$C&ccm34F5Q)A8^HhDa73PV)S3b1{Ca37l{#J5AuD1tvm-zvJTlNM^4j6S$oOA(S%tK3llc$_OV+;x8s}AFRl7RF%WEgh<-&'
    'LLBd-uV13ujvm*jVxu7k4eQ&!mS+u&1gSG4j_-IyLa=;VE;xNZH7)Ys7ZsJ4T@bX^F5n$qz`MDCzxPjudspd76e+Pijn$1BW^te5'
    'ClTJ9Ct<rKcgX+gsbt9DGa{PC$asu?idp|Yy6eLg$Z!3j3k7+a4adL;MR_TL7Z)64C)B1jba@D<K>;EJ0<O*PRPP%D1f(w0_}#ME'
    'BIH|=b$XKsq5iYgcE4u=p)CjUH$n0=9Yz+`lFn5bzv(`_dvW$43K=4G=hm5vk2l^*bfiRG*s<u779``o=eVcr5FASps5wbQ@7j7i'
    'o$c0G*%45|;otQF?e5O*E$=O)Ta%9aGh0pT&g<m7K)jPscU6I*8M9tXk%$YXP7$KMDiNB{oy(TxLsg3jt6DHa4l*wo^<_Sh^5K0r'
    '1ZzcX$N5>@j5+5bg5x`>NK<G(*X^WnBX3`3`<a~k^_J>|gC22w*qgfz`~@C@#lX^vQtD?Wv28&_B0^yj`Anuv&2nvNcxbuhnKH7I'
    'iBMmSle9Mwj!5lJqYm@s;J4Sx>1ahVerv8xM8i8&8pX9U5)N(J7RE4DMNe{U>J?fVFK?^y>rX@`IiB4AZMqP&;|uw&m3*J3V&nUe'
    ')`{;!+AXdR*PG$`Fylb`a<^M_gZpr`l-yY&Q(H^PV+b`vP6#9{jlD-s-+!iW71KvT3E5Ia#L+8)$tqF@@Nr1m4x|a6_RL)J%Uz_B'
    's+q)oV63pL%Y=9xCUGd<T{ql%>WIJe!_e|v`7gvKOxHW0<X$vOfKTG#N?^;KJeyJRQx2|6@`Md3m;?Vm2|r{4C)vuvOyKX56R5Zx'
    'UK8*-auM!D?RGQsDPE=f9~0n=yQ4FnCGq2`qN6jIOA557j;=w)1>wryq#C0iYqOQ^$ieU3Ye!^yO4!Da4Y`duvb+}c(Sib8wBJ(R'
    '0U;wF^%XhsKCRwex~qCPr*{aXK>?h60jno#sf1q#G~|ai=nhqvwPdhz#ZFpgov0-p)cpk3%*Kq5AMqulN4ZK2;t7*SDtX6|j+=~c'
    'c#$l|Cr!~JK%KgK;SapsbS)>;P#UQz%L9}76hDOR(E`4Ep}O3<$V%P@uB~GNYw1apCezeUtWGOm#D}O19{WONw@`X0FOl~@@`y4P'
    'MJBqTKie{?Pe`jkKI<(*r9_3T{GQ-%0O~~|=NKhE8!@#z%Sq%xV#?bi6G#2yj1J9uLnp?44=E6xAD@~C!H_}A2sHu1bVA>;9hZ6Q'
    'qM?z{U$E#L%ec0e=p%{tVwPV=vboo^l~(BWt_yWr-&baAR80EuvQ7}Ir$l%a;A-6^od#_vUtN7M{qV#RN8`CYp_9Ts`qd(-t^Xsz'
    'RSD^YoJ6DavU-ivFyz9k?;-gnyEseWOr|*IdR{MB9MQi>JTQ!L*nEwT@c5jyQbIW=lTM!<Pw7)_pL;yu3@M*;`rYa5*K9-GCp3}%'
    '5?7t7BC7z~1{_$tgZU-O0g%FGF30IpGD9@lv;(tWcWfH#%@xiafd6QJEgZdlRXs}Pl%8`2odFp{Nn*PL9(s~{Y=mVy;`yq{BxhLZ'
    '*EGt3gPk)%1{*RzlKeyCH)*sk5VLT@)HTtJ$MnLI)x8X4qFs)D-gSUT(PF-UuKcc=)*1jw7!H4M#v#`5Phcv{ldU(8w_V*d?w66&'
    'I~IxiDZDM2X@wlRRhdyhmX~b8-Mo)8N^x^mwq3hw3r}ASTH4g%GE6^c3uZnD)G|1WN+}Wa3uf~31gG;hh?2Z;Rght#rz=IcY@0A6'
    'KMlheuTs`l#Fh<KyrO-D;sewz`1F0G)XMdMHQKAxV3R8Swx*V1GPEP*%$Yp-#6%kf<%4&eyhu_oLASTpN>yKni_#}qm7I+VtK{c4'
    'PZw>3VqH58z>`YCRK1|Pg*uE0cg9hmBxkV~iS559tL;sTluOHb6JLU-vJV)V#Ze&sZFHY)V|cY*-qu(&5NcVL#{to|1d(EOf&60s'
    'kc{QhJ{4EV`^7-r-#v^`fdyVrZv;7!GN~dTrP#Nt90+10Mv)1w!Ag^uR(g_Me9l8ZHmFsori1k#%im4qFrymdCkSpuc6n;|;?&0?'
    '>lMt#G40!<y3ZXiGQy=gMD)626w*Wb1Hpxl@jmFM)FH_{z>Ma259ewIzwI|KFzPWj*lGefEodG~rqJpwx^am4M9&llX$VfN<q<9h'
    'FMiD|Lb7Jl@HX&CU?Ly$r}O@JZ>tlgS3z7yocrv=H<+p2NRq3etRZlXvis#UD?z9;dY9c3WMyTSLLM&TIF%Do!p+d~>tz*^FlzwB'
    '`oKjaB(E$%zC?F>ByoY#8}Umz@di3fxkk7Ha8APQ*>u0JEMr~U!J;_DacWep@w#MZFCh~wtJFf4%UCH*N6OR80v5)lALV>0VrX77'
    ';abO;J&yL3)$KRh%v#+<eH=4h7^<kv(oSnDi7!f~H0?!>z#T?=`Fax7)KKys>#<78_p-#$z8+*kI_R}o{g73SK(McEt!`(f2kv_M'
    'kyk0E!0d67iF<p~rI_?57w5@q3vHJ9ZJ0u$C?w<54~u8bnnlz3^&^l^5j8AF&WtcG49U*LD3vLD1tHkyq8bt0&f5rNJ(ZrBtq#50'
    '645Ev2$;Erkj%@547bECYB<bn#Q8G2vWzFv=(gw|LDYj8rA)*@F?db!BS9jDdi3N}(hnPA@gb*V94;^H>FXh!uOldlK~|qo5*zmb'
    '8$xXHc)BTfOGM+BFl8t~_^j(5x`R{=*08NRe5+?Z%*|AZkh?Q<*{O$f0K>wQ-C?h@7G>+A-1Jj*@yuHA?H^CD6_hD9%eD(hh?2D5'
    '_(^(o@wu2RAqY<?Lkl3Y-Q|&OBzx<mF${^eBe%h9flOk@1(B3(G908@!|Y~Lp&Rdo+JaU<E-eK9uXGC;)QH+pFt_7$R1Tpu7S8;B'
    'RPepTiomz|iTaUa;t^X@Z6tQp-{minBrf)_Nd%1h<GJ%8*O;&I{Za=AU+m2o#(kD)RT00EEo!8e$!Q8!D5dcNE=|BzRyeEW6Z?-}'
    '5CQUTn?o)Q<AiQv!8~k;`#|XK%sY3}?TV<iLy+^8(&)oEHcuSG@n6Lb$w&b_LKdElWeCT5HpVvRN6wFb+z%-DrawGBOUNNly$yci'
    '%IS3(^92^{ZUiY(5-c8VHdHCcSw-ldC09h@5*&Ml?(RaI7VotcF7J-`$9BIf@5W+rf?P3}9U!oa@oa32-lodk%=~c@<*x+GKryW6'
    'x$tpC&V=DR>JHHhaQJ1W#~Zsnreo@SZvHT%BypWD?TqE+hk|r<OR9=0j~_xvdif@1d*u@w^}n_taQ6dw_Z6YLuasvcK^`K*kIMcy'
    't4c+R4cz9QjB}-4%q<}W&hK)I6e1(~*bGtSsCf3=`zSMV*9X4hhk-$iA;eiCf@R7kAzgM5V^aD~=kT^8`C>lHuU{oLRu3r7R8`8t'
    'L-%mwklJfBDIx~TX>UM_pk0$}E^E)zSaXle&>Y4*{y;|FbGoB%0VL=hZWUTn3mt!12~huD76~)*UdcYg1|;iWU^KP5y7hh$M73Bo'
    'K}9l^x1hW;9*BiZUj6oVM&i+-eo9XJ-)gx!&)9k6VRBa7oj<ot?^1?Sdu<S+7-Faf&_07`H4^V930WjOY3T&0J}5ivCJUU1Vc%n^'
    '#B+@fEQM8|DfwBmR!M%Ku4oL^foF}bO?N0TNr;C~w5U1+^b^E$jmC$C72&vfslrgnH2zt=5y!drWx!3kt<cy82!W4WD+S~-0Oy}@'
    'QVPU2-&l7vUj^L-E({9`Lpl7S!?b4bN;z+8Xi;$B*-R6lW+(mLY}p=?MfZ?4N5Y2D_L*>W7_2|@&46csd1hSb>6x0#T;*!CnKC--'
    '$NA;3_K-7K)}lqrmaST~Zr!F$+qQ4M`DQzGly%LNDuXm5$si{%1%6}_ps4|;|206goBHpI$%;QRk~e?7P7*0RVJ!5@aK?FRp2Auw'
    'Grw+K<Bhqg%%aM#o}!PCqM&S;DiGj9{R@@rB&i`Qq)`8lFt$d{Y?an%Csuw=(^8*gO{fOglIkJEK3YXLN~<j|>4x-3_YkQKh_}ui'
    'Hkaizb(#2+n`aTTTj{5CPZv_(EgV^{i>mTRCP{n-jsGdr>K3p088o;Km01=!f&K%cD^23{2tmURKFmruIwmCN==;Cbd?((>h+bQg'
    ')mEYK{CFn(d$y?hW=iN#O`kViaBo{+(Z6*=|62h_4V_q%d#;<AkJgpR`9SVA;?%iOYWgGew6P3Y2&eY^Q|1?;cw$#_lU%v&HSgEh'
    'AUU+mpPWaTxcFcUcvc0oSL%@}k1fNh=3B^?^51ParN945U{2|8)c)P2zxhU-7D1p9=7T?`bBe@}j~!_qx0L+RqR8NTQd(&Sec46c'
    'GMHvTPm)*0u){5Msl5C(px*aef0K9I1=9QeQx1+C3YJ5`awyn;h=S!5=LR{&xi#_W-&UMkQ^CrLbK6weBJ12_qu(Vl^CcULoZ3tE'
    ')m|*4vSbfc(!TuHvhAe_Dkn_EpW_k$n)YvaxububQ14<W8#nJn9;Cm&piQL^=ORzxW!kR17?YKFc5Y=8qCnzqqeVagoGvcCj|f?V'
    'V@eEF80#RKx!oXd*)$>AF~-Ok_0VjSO^nZ#8%l)-B_9q7>CWlWfU8>|zRiD=TgfSQtOuv%6gw7-R{zRk$7D5}$G=~|E9xmRI^bjf'
    '(hH129FjaDe0XbXBTc6<T6N>wIvFnvZDBtLafYz0k?b=hfyhRG@y0gPgfZ5Dk<@&-p40JHcL?>r3<bc<D}Z?qJ^eK4%qQL^UpzO?'
    '_;g(pIc!NZs|0SeT1F-$k(JrxXWCw5tU)_Ud9EUvGTBr2DIsyr3@+FSa}3|ua?fInV%3F{P7CIFlScRd!k@S4z^OT4l*O*}R|}Xe'
    '?GC%+Q!Y&m{HJP;bJCLMq$SURv+%zuEqRkIM`vn!5udSpHyO2-ogsm{=%ca}r)BmRdo<B+As5pmK`bdmcf=BwQ`JSfCxlByku{k<'
    'GO;CA6)E#+vf5O`0}i;Cv`5o^7TX+uXROEnilr<kB~cDMCneE;FC|egVAXp4rC`rMtLB;GM(`Ij>re9k^Ev;SW3AU%&H~J7|HG}!'
    'm@`GVj`}}4ah)05LbU+)n@p5dW2l<F+JezczX|QSt658P<rE+!IrD(A6EU2J&wIci#cR%LoccUiJI@ZY1K+@=G)4j0T{uA%J?RkR'
    '&fAf8(WnQ#w(WMK?n>8IdgJ^i*O>CH_8v!`X5O5UCubG?Q(J}aqB5g@WOH5AL^|bc##x;dCUG`5x=HBq+PA5SjIKmI-iMlxbDt7S'
    '>(Ev_0_7fau<m%3G->TL_q02V#z`n?W|UCGwZDk%34uu|F0!sErJ;uYZfQm}HwJFU(~N1THJpdEPuVT2ior>9d54-FJ9^}-?*EAv'
    '+;i7ECPcmD!W6wu1W(?*CqQ*yTw@ubF9Nk7@%?;dB){B!W;qGOKLFa{t_8}E0WA+5-j5zv`2(Rel+$tfCZr)`j)qyRiRg@QNN7=c'
    'F-RYh-^m{rIJ_rmEPTM$!ofkjBEZR9*scm2&S?G;-QM%rq(dl;I4ytz>oIkvKh~n5v?N!&D$7yz15V~d>qx`k6_V?jCPBgxP)}e)'
    'g%8$CT&9jE&9=p6MSg?wDA;=*P0F}2EqBi1&uM>4v-ducly+%6+FH54yq^B#$orHD#76eZFq>H}?7#IR)*;e_yT@!y-k-^$^`SMB'
    'ED0y*)XQis)UvE`aeVoxZ`T&xCyKfyc1mNiw9V#suS&soF$wcp;6T0x^i^jvfe!&%_By7jfL8d=k(YUVCLL1?h72I8#blm^_VF~V'
    'x6K7zr7qcdu^MM7vO(9r6y5)%pF^jHJ}^sM1}$b#1*)<g$mzh=7HV<gX^s%hLGS|d0L-NY%Wu(H0F}I7d>;#_Au9K?gS80nSlF0;'
    '*?i~6m&;lFIqmOlMW+6lm>RaC9@905m=)L3$o;9hp5_R)cf7+YZ%}a$QtS%z`I=q0EwAO#@|Mlv`?RbE8~MIOvp(5a**$#1jnBd`'
    '5I`?TGR^pIDj!1T;2S1;L6K?apQPPhRqy}G+Q>KWerEW5KF#cFza^#o!N=|9nsz%Q^6SD(PhpfX<Swh<80;k3FKNq*__t^#l4+aK'
    'OSYoJ=psRiVCsThUZRd?eA!8LJI0OCi=JiFZ>f^Rkzutl9b70dM7O(nPfz1L>3i;xyyt7i_dH{m+wkJXxt(R4+Zfh8D|lXb)`La)'
    '#qXJVyo>NX?_@q)DaqLD*=W*%>yI6o$&ar5wqjIE)&tVB=Uvl0dZh@Po=uVm9M;uf*pd0?`reBFD=X4iT|fz}9w2E{VcI?7#OjR|'
    '05s$QW>X}q0Z093=)ze=TEWxjfgv@pJ%u<}ke~|IsC<%SUBN;^3Y*Tv?ul5hK<qH{hin_Q<K-Q`kxUGOWWXOyJpk2q)es|!TXTta'
    'y`EdZ`e9*|gx^Iu2*Ro{f4PbfmcX@I1n46HRwF<!nfizTbNxqOC5&vSaLKFCC>UvI=Qm=A4BLiVC9rL1l~e-z9#H!w-*B=&z*5pW'
    'VPPma>C2LJ@-bZ**w5k=16)Y!Le$dve$o!={-)T9A4Z+XJYw|?;DJ47_u(&-YdcGyf-v-Ymq5j{@>tDdR<B&*xrq3PJtY^cGj)xf'
    '+=p`<=d%`;?zi>g!_17tdq=+;^9E9mC7K(LJpV3)0COW$4lkM0o}rC+&LHfNq|whea0ZACc)l9~FzWekC>o;NzoG83_>4CM;F16H'
    '-OwaB(e(|V{gxp#d;0L_yP?W7`#s+cxmpy@a>Hl4We8XHZs_yf5P*k%&v!!rhCJU5)m!>L-wjPdW?kP9fGFSRyCJTN`Rq3YAkz2w'
    'ZfL@&y1t=$OP}Yvp?StD7dHeT!sq#J2*7~nyCDD%e4g)yCJD@3-%!1!_w(J5WY>S@8>$?&_w(J5Nj>{)Hw56m_w(IQxMdGbK2e25'
    '8?3z!bH}#=PZSuV220~M&{D|O)Cwq72A4D?^l4UgO#i(J-s=D!LL1qe&0#&U1E6Ugm@MumP@}wFChY&G?fXhmB4OZ_$J2I7NlkZ9'
    '1LRlUeQeVU%2f+$xOZQ}hBuZrRL|L~BNVT67+{v$*-)tsOZx7h{*;wgUTfI!w|xz(D9U%=D#}GI0r>@WKqidr^~`u(mF<ZAJCrWr'
    'pOH9KY~`Ko^h@fN2n++4!%t?bGujG-d;MH*Ow?-SeQ?{3@X9&Cq030D7zH{0%UT-y$}?i9+UMt1UxCaZ^p`y{LA9}WmaA8)$W)+V'
    '2Dlr0H4BzPsQ+`MGx0=!Pxc9*k`JjHdfiMu4#V?2PTdcLq1yYqM&DIs%Ar~fhtaCwvIJCDN+f@e%mQ_lDWHY2GfvZaj8r9{WuRI&'
    'oC=|0_QCG4w?bp~R`~7dUG?bib|dLXm9;6Q&m?`Y8An3D3PuzFTh(dT>h}4Co$;s)R;b@X^J<xqRZYpSLThPymugw?75_;3Xd5(d'
    'c%0Vi2bJFY^p3X2N^E_cxD#vlk2+^hcOr#@clJr>dw>qPq<gj=PAtJ~1lPeiq~Ylh4$^yg_+1_aJ#EtOgOAi@yIjeg44S@}p8E1p'
    'Ri>%~B4Pc<WN02K103Zv`v*)Zu>&NmI{?zNLF6XIf83RnxQ&(S?2h<47=V%<00b+ks!;PV)s3Z?Hx@>9E(QnH#gPH^aHBw&4SKIG'
    'QWV=0X!OnlKqJjXyt4N1i&{@Z4GLxG{a^uH723X1{{o!d#hRC|`j@+G(=6Ae(zMdtYrswgrc=!>uEmP>)T}u$fPSe4_)-g2M*l9+'
    'dUj|b&yQiv1T<<j>@J-S|JpWe6Q2SjI@>lM0bU$X=!7~^$zY&Qmuzseyi)LH!f17_LcZx^+xD!fMLz6CuF|8;uINr}*eEP4%;`}7'
    'scAhzQ(g#VW0dnS8{K)$>FV?pbqX`pCA{!)kY?j{;D7DDzP`fYa~&>C?H^?_<l%S1nSTWGD#gGZNdA6=Q#l5z4_=2U1wzzMcMp1R'
    'ZG~F#anNN)Qv`JRGc{&;kmlBPKNakUcJ~=dS#^dBXy5xV_@c3<yZHueYzu$~{8oG0X&1}D9t2tsHiQCD1*X-UsM5@@l!{rPrqa?0'
    '?xktj06Lz}csLhw(cbfrYNFg(920vft{b{oTGW?lEuQCM%l-oZoZr8PI2}2ZT+?o)MQpC5Qd*T$$N*1Ez7U_;Mk$s=sxw^1*%GTe'
    '5XC6>0Gx$Xsa`AyE2;kfMk+W4iBjEE@I5@7{O^PPnl<kO0FoZ7ZTH7Cm?iHF^<JA^R6I|E?1(IoRI))#T6N{c3{rOJ9@299f9TAD'
    '#kW=ha6l_r{?%iUwg#yd%HAb;VwQrleWD+gS3+-q-Nj>oGbRf-TPx*O-%EeEyD3tYrV*9#9-=(%3NE3mpoe#dqN}B#%|Pv{ZuU=#'
    'cIA0Kxj4ES4%drzMJpV<H+#R@u7juh5p^6$)zawdC<$b~46Z=Ty2=Amye$bQCs)bN^4sYbIw`?WEtCzwEBV&1?`kW02a*=pJ|j6*'
    'CxW;ZQAyR6g15nT|EnPTUIs{hNhz@CPDb2TXt1rdFDYU7ODf$>0f|pROg?q3Zt%!+{c5Xx*#HsRrXaoRjf^XADV;%9)`>`vUG+W4'
    'O8Q?1->9p!7&KO&DyzkMF94^ME8quP@O`jYY2g4-Pr=hNit_rg)TCY2sG4y{WB5%Ur(g$0uk+Z*Jq{Zy%A`4vA>(Ikm#zsM$OgR*'
    'Ys3ALF~`*$;KOz}NnAc1=dKT!bS*XN*LrZPrv7{tWY#DGOILVDfjOl#3VRYPww(s60&AtJTe$$VB0PLYJ=xL{e>xA&6tAJ>gxL*#'
    '?yqq+UxKK2v`x1MocFs45`H=Zt@in6-AH}(oBBO`zPOzk{dHbV&HTUt{;<CYnb5k~pj~&6?F~Qt*PTJO7vyOU{Xh1;10ag4Tlg+Z'
    '2LVMCd+)KtZtNvdgM}#e8l$nt5__*vV{Z{#>>Vq1Q9;3qf`9@777*#ZEG)Zw{(J77nVntMnB>d%-uvGBN7=c1W_ISzoqJC&4N(_b'
    'J`IBCwThl(<kJyzIh~uaf43Ope+$->c#__kbk@=lJq?<7EP&f?dt716LUZPVYAt^L@g_fWFw15&*kn#C!%aF9^$mma5VQ{?zpJYy'
    'LC|LC4OEpYI_%FzJ#qDAZ>UJSp#kRpQJ?E=&X9GOU@qyX1NGTnj0LH>B$}SLo+m<Wzb{MDG20BgDO0^mMN->!iV(J@raIaoOxV8E'
    '|Kg7yt=pA>){??I!;{~$@s<>T*NfOJvgqec5rB|@sPSudJ&W%y6@j)nX}p=97qOrs*1*m1WIgY8b)X3urS;X!oENj`fmUiLN@Gq_'
    'FW^yW43cYCCbf{#d^5F}ho+XO1FrNEp0Yt|@Dco(ozN@-PI480OVGNQez%4#dh5NBs+<T<F=vPMzM}IZI<y{gUc-GftscD=ve163'
    'V#4Q+56+~|^Zdt+G+$58u|wNJ4>GV|>KB_6pp<R)5XxG-CU%L7X=gsf5E8JAknnZHLx%x1FHRA1X)7T`6Ucfj0&JN-o06o(M5!A{'
    '_6HyxqKL|_fKtQ6pU7&uBo+6d2APfG&b4!tzgXG&*!kQc6Y?>lcTiz{GC4MVoAvhm7c4!F+06)}$~(@tay<Kg_4Ux@cYQ?*z`)C~'
    '>fETa<0T8q5?MXB2+)bOf}2CyIZ^Gl84e5;@)#&T!nY+<zzQ^e4e1sX*{}e^gBY+l4Bk@uV=ZJyK|XXK6yZ$FK-<$rUg&5dq*#<H'
    '<lZ~3T5uZ=g<QRU503MiSi1DPXjX`Z)ZpNk`OMKLnq|W+^#;4j+Z1W|3vKgOsi;&El0Ie6QV73&kqGJIrSnIEuC>@!YGIbx9*PK#'
    'oge%GAly#4PFBcL6co%x_@oxT_eQD4oMJm23VX|0%KY`ENZGvrZOl>xaqG(U?hRzsLc7U|?{$?~$!h7HGzp0ntc{+RdZ5*CXBpzO'
    '8q+N)C;`@?JMk_g=zT6HsXt!rOZYQtl5dSMXYJe%m>uPTlkkiVb2Z303D30&puX6ygoH<EEAnBD*fuMKWn#M)-dAYv0!>-ow*Fa*'
    'JG@tXA;4`rVVu(g#wm%chM5ODg>B!8S0RLavMG3x5$R_><j?#}xW#V$jlHC%zjXYZ>_?_seA^-YV&!LlQM^S+-%APVME?nh%@pVt'
    'mqVq_JNC>#=jloumZO)qB0)$Gwe#i(H1!W9rX~o^kgtf~kp4w&9&LO#I28F?%Jng>t~7r63E*%=V%2a9eo-6{j9a?jkpJs@IjJb)'
    '`KJ2%Ub<rfw7=fgCr>kM@1-2R^?<*3O;7T7KZMH2$V1OeO&7W9nt!!1`?){!_3b(vpod}uXkAMt0;pK6=NiX9sACqJi#JsK4*6Zg'
    'FTa86YjH$31JiG?FKeLCO`H+SK;1{29`vH=Rit?q84H0{!k0%5t<^%cWp=e`f*&Bi&lxCaCVg>u4ey+#=Wm=3H_ZOV4E;MTz8>yN'
    'Z$27Z+Xd|trJ2z}m7`0-w?r)KW|N=9zn#OPFMZ%5|27T%8ur7_{F{3?R5we^`%?I}24=Q_b9IGpt>D&57%6^Je8_uNR7(7Yf$+D9'
    '^zCazX3{r{45%o6V~IcPg?a0*Z)?y@EwoQVl!e&-j&@OOyAOa=C$UW)zy_)P6%^DG+r$e_W{d5bYEX-979=9Joilji!EY&kNWVMQ'
    'Tr{p@sz6^m<{z@VEOA(@g9AkIL2%kQ2--?@McP0IX=GQiDlzTJf-Yj(JO_YTHN*;y%>V|H7@@G}?@-``9wbM~krE4Z%#C!baMQC)'
    'ciH1&k~-nq00{$X;ty8FW`1H~E@d&x3-h3lmP*&clz2e-FroRF${oD<osLmYI#V)P1OUHS?6#7B3Wdwk+V{Lj$LG!%=EAZ=5Xf%X'
    'u(Cq?DE?fkLxsb8!RO{M6qTzjdi^%1;y_oC6D|QTznl1l4%VVN;%SX3ZKneqAUGuGs*o7~8*GVkj2f#(C{F?8N79D~!!ibnk@xce'
    ';@65!AeD<?t=?^S8(r3sqTiYMs`silJw!s189dug7{{a{06&HBl$IN?Q^FHB#2kjaZM6+FmHGLJYF3L;SZrDC#S!YxJuCS6x8RMH'
    '*lw!B2m;}n#~??1X{1^q>Mna<OD@Wf*yhB>F#g_4fM<v}PSFYCk@=zlNz+%ZxC+|e`|$D&HPDqu7rGodXr<fE7nG@p6$(2z&DX%9'
    '&UX`-($o)*RMEj1+HRIfxu7`!h0*c!+%j}-U3yoT7y7G<ET=~E8x)aHuAhE3;%X4lj`DABYEY@fW=Xq$tX;qz**hcEe#>R>c>rbU'
    '#MO<rRJvuLQ&|}*(rGB0l#GISsr3;B1(93I;ZTPXetw}7Wj9&C)<epw+2$}~sH+asza3&;X+J`S6>`>^()crU5jBga%z%9X_g&dQ'
    'dFTNUtKcq8`8G#kEr0Y-_%>NAV=)(eq^x5VwK7Zg9ne<bix4kNS&6lbxlbVbSO-t=OqKzZ4<F9T8o$@%sw|0lK8(X`v0dp$SOA^T'
    'O<3x>C|F25;J{A$2;*28vAy6;Ho}ji;4Ez(VVrd`MIa4p!$&$RP?1_5ppGibj3h%H4IhQqum)WaFTw^Pk??LvfTgIZO%fa!hj53V'
    'c2WkGasXNf`mPH(j%}`CxUftH<!Z?~NOeYa#~X@7tRtyN(n-j8*G{MF`bx~PznxP3OriLZeTLqT>N^Y&;w#=U9*!0X%91_s+G;&y'
    'l;vXi*TgOs%a72@pWxh0SMm#FmE$xq(rO|UVQv-0L%2uGp0jx}3^a5Bw9!FlViU_0(e!0MH(LTpY*m%bf(5yvXgdSbVT#q1LP0CZ'
    '@Ec^M+Wt~oB;*^&6I35%N_E-x!#genjs!JlL>uG@He|b3Vi40&c*CVLDyH#*r(YHbi_9@vtg$$sqAsSJ3XxK-d|)+IXVK52JG$Dl'
    '>bd{OC%+oK@-5UxtwqcJKs1NcKpPmz&^h2N?}&jNKchN^zM|Tw^jBo*98sav1+{K-0$IL`**hMwtQU*^kxzcLKrxfXJ~8o5xq_hB'
    '%o5zdICwg9@o>m`qqIwlx5Sk?88zc$h}FjwI%P}ehbzY6^ha{&{x2EtDjpTLAG#N1;9BdI{~R?Q?J~CiYi2=<#S!@*PgZ3MBYATO'
    'gj*7&*WJO$gYgNXuw$No-#uXY!`)G#x2|V*Z2b&H=BRlYfZD3S+lluepa)qVpYPYGWk~#ViX>J^<_1%(6;t071h&FfNbI>ZNVTV}'
    'k4{KgCvXD=iJ+WnFvHUiD18rR9<Q%qD{Xx!fy}@d5&}`t$5YYcArhu9{#bAiNz>pb`DwS>V+AYSRUc4yw#h_fawP9mJF#eSUorN#'
    'qnK&iE(dLjJM-_8S)lX2qSH~qf7G*r96zy^drhfAuu;oudrIErj@a4=x(ip|)0SN>-f%N*HDXL(OWNwjuxxeOYQlJ%wzO43g$1_u'
    ';%|4+iFW%H_Qw8TcD7e7=14jwNR@T5HmZa(e?6j0bg|DvdGi=7qqp;1wdyALQhb${OShm7z?C?Jo->D@lQ5Gk2F>XUkW`5-_K<><'
    'vlNXfHYcn0A;W!UBKZN!fii>cg$Z{+wPPF=2vV6?@cB=xZ7F%zY9I@{9^mHPaN2D;ep^_aC_Zu<=3iRuk-y@PyqTYeVt~)R*VwW<'
    'kez+5jWn!H(6fE~t}#eAaxCd{s1F`4VpfzX!MUnu<32f~^sVJXU+4Na#@4l*=SA?=lD4vIV0dZ^+B(Si?(b*|3%Q}Tga7tVwsu}0'
    'DZk~P{h-(c3G}w>`t;iz^7lSt=)!1nA6H*TRn|V`=f`9fQF?=)6>DvSP$veP4zU&3(Z^aI5J4F}9na4f3_h*YEK@iBf>Lxl-YSuR'
    '!U((aC@5<9*9O7pBMQEs{4wjGMX$)5>*diz=A9A)usI``WjG3kWEV;`DUsfShK*p9ws)X)x)&M&*#*|3si+g?to&EL(ryS7CJfH~'
    'qZ5XF<C9q!^{YK4%Q|@El?6{Mt<#WSqn!Wfwp@=G3J3dgHu4T!`ie_FFJZq`D#}Z(Q6{9ny?Z(bZc=Wh``w(v@Wqyh2&d0{SMY?c'
    'nGgtzJ)aKAw)DP<C2{%uNLy&ejx>otw{Qg71T}=g5EDfaXuLITtz5_vXs}f3^^d2N#pdL^YYk8_yq2PY+w{e?uw`g~3V+QTvS({$'
    '0u8j`XkY^qq8aA9aw`&Bi22U7lF&fa&$sA%+n(JYrwwR^)1Ik1D=g^Fi}!P#th*+6j_adUiDxKc^oD2KE<$2iWf9QlKlQ#py>i;o'
    'iD<oP$P#+{AlFpEV@oD@e);@~8Dgeu7UA${+x|2<*yVP=D@eIF2&o7bFC2lwC<}HUKKnJi-qC`bWJL{&f1Y422kR-K?n^2?EKD9k'
    'a#4rG=*pjH)xuU5GEJSa^$PBoDKB7)zK@u9UO0E{b|+`-v)4lV`)pCu+0|q`tE;yWLP*I%=!3T6S!iVZoytX;av0~HY_^7F;Iz(!'
    'uOeXxXD&}c7V|6VBBfF`i{l>niX_}UfILfLQv{XCDN2AGiV7*PJwzd=d6x8nLrlQ*#6EwZ*r%DwpPYk%Ol4l-RU)~qw*RPeVQP~}'
    'R9;yC<GIK)62hsd(F$I1mzfGoE2GR5gAXDhhM>4nR02&vs@ho6#a~Ie-1~}=kWq!M+89`t#sh*|Q(1nW7=t6IY9~Q11fxE$Zoand'
    'Qxv8xpHuqOxJcKH@^^3TFj6tz`7{&dDD&{e*PwMJ<X3n`6mQVME)qQ^7s4INEvaem%WE_)v$<L1B8>In2Hjq8r683lY?L1a)f)@z'
    'YA#x+!vx2(58O-8^;RN8F=JN6%)DEI1&D{9P!f3d!UbQ^0rnDvvR5(_a+#g6rJ6eyIK36Zk<P(OTR}Db;_~Io2gRh_C`wemQ-BEn'
    '7~~(Sg9~B-cTpHD+r{DwvYQ0jx@ZJWN7&*NxQZfGWi@o>0^eYR-?7Q^jOSe63o5*H+3PBLqsu6I|8pNlAr<-YQNAouI#I-MA?7ys'
    ')AixIn>-QFMtIYd_PN9nrj2Wu3c>AA5W1pZXU>-W;11g<-l3#8>K<d=jzThyjP<Up*Z6D}wfjRz8XT}Czx41}No;pON)U9fk1DT$'
    '?^5<!|9QT<-o?b+M>vLd@8Qu2O&;aIJ3yKR*%16K29~~%4AH@&_lQ`qbKn+;n=pZyM|(>3WT%P&f{w2<>tiT?NTqWS<>TX<3J-*Q'
    '_36jT5Yj9(??zSPn7P0E{fDFlxRBmj^Ac(MyWM+8S<>gZH>>^)5n}q<UXpuDn5-md@lEjpt!-QrbzdhYueZ6BYE-h_W_6V6!$AyO'
    'It?E-MZi-tVtw(h8xlhyiAF_+dxky9;<@rEPrI~7e{8M9<Q-FxXP}bF1K-#uaJ#eFhQz#^wK~1}fLaUEqA-s~W;(x57iyPye>5%{'
    '@o((GKQEqG7YN4gE^vf<`I*(y@fyW`c>#i-pjDti*7peIiwEkAoZA0saf1wlco*_TUQ|_L5gAnWU*vj8!;gUt$?;`~*L;uVtja*`'
    'ZL~WXn{dOx|KQ)q%dMhsH}xI&02Eu&_HU!yi^O>K0T=jo><?C0F>mDy#@pXf5;R7`+pg!d<%@QRSNK9AL|x@)wqV2v!OYhzgmR)~'
    'G?b{UkN<NKF69fylNBkHxG#-0S7sn0K6#kbV8r_l9Bs^qs4pCCB2m+SVY?1qHJS6wbvRR#n`f^6PHH1xZk;}zj8{<_J~OARRn*>p'
    '-4}auV%$j5LI<F!$9(#RHOF>c3jbiTD0x*Dt$qO+TX$B1q!@sd{w+E`VkV_&HsPR(0#rNw44IY5ocvd2loB2m-KucIwb`No_P1+i'
    'Cc#h;Y4HlY+qJXg<}0y^Pah1z9Hx42Lln0`8>MAlqjsA=6htqxkhv*!7J_1<oBi!kQ7kqBc<34!lMln<;1u6#>lvP4SdpY3ixbz^'
    '22=zaR^VbvVl;P&sZta{M)CIUQbZ}k`&xTaU`2AwNHS%dshGwWo%O1p)=paR!;(=mhRhyd`r$lD-=1{#FDGjqg|h8VWcn8b)m*#H'
    'T$dpJV1fCTTglI~Gp$AwZdq$hnRB~S!S8)*Ok3A_)`%4|w<E;y*4ryc8G2oNG2cqjdY1G1OT${vYWJYh)yUX84fwCBTs+g3vc(Gt'
    'S@LaZFXD8UzS!TIDg22ia_tLympj#Z-=w1_%`13c{OY!I09lUm|E$p@fJ_-dIlL=`+$XELPy$Ftc>K|$l*ie7<`%jW)%GGkVx&-+'
    'yEX3P3#ygmjl)+zaLg4ldKB3>f*cs_SAi^8OdOMbr+vL}{nn!EepRRZGG^frdFYmz_g7>J#V7AvNnOh2e0_=jU8KA?hStBO?DUki'
    '?3|515@H@g>DolfpVthflq{3~)uf#B#7)FJv<lgPX~mk-QC#PF&D(<PyKh4(Z1foTiHYXG3L-YyCw`826q5Ytyc|NAb@UO`IFZd3'
    '<OG=!9c`FP2keRBrGhl0b8W$Bii0YU5)?c3r9#SYl&fJ}_qf29zmRGXcFKEgCsW!zW!-8@Zat2!qMrkgOju9Ij5QS^>@5RZkO`5I'
    'wC7D9`k+KO!iO0+{@}A(*qhw21!Q4p=w7o<ftE_&euNUhL&*BqjwngUmthncws}bjxl<&1E=<V^3k#d8SR3-<n02pPX2g3aQId*J'
    '==3?B!E9jGSHHKVICj$R3FpleUQ^9ILqZNB5;%mnboZs7WdhpL&vR{>_>eKn3H{vW?;n(j<J5$8i+)zkr*~=8h^16&&zv}Wz43o_'
    '*s7A7nb|282{~rp(0vLsuL;&iLW8#}Nrx9NPgp7=YmsG*Ix>CJD6b1oyllq@nUj69dYvHT``z|YF68JW(*4o1gO<bT<v*h5x#BK*'
    '#EjUA6DSm!ihe9<!!Z`R9*0^Kvm!bkW?S$29JTrS4t>h+YlW0Ab*~-yH6rMQvinU1**$durRih$^z~7YeLs<P_irDtB&&m-P9fbN'
    'SXe!&JCnYzrL%ejm@98=B3nalA7Z-y%|BM%qHuXzTHzV-Y9N~eMl(WVSU3eIk2ztn9n}_Jav1A#zQ5(HAjCyZ6MZjuAk$J~so?H9'
    'Dv)lMinsYT@_0{_FzT&&vJq=Eny-FOzF7NgYqQZO-1Mo6SHwi0aqM@`mTXyDi7uA!5DnVj>q{xaGZfBNEYe@^C=X%kb>_?&ZzeIW'
    'T1jWDauvnDZW~?Bp5L>-!EJkT-SL7ush+Le)Y$U24HX%iTqDP;RXlE!sIWM_#^E-xzd?Svf6DE_rKXe`>lyg3ZsAL*%hFP{Ja_T@'
    '`CqGW!wGjypT9Mn?O)djK$6q(F`0_t7>B2mvgx+OA&WkH;&3tnRXF`_lc!h~&my6!t0pWgYNxqtDqZ>E9qCR{C%TerQDESQjY<S6'
    'JQw4R^t-~o?fnIR@am8qDY-u`BA7no^{p19T40lAF+9P>NP&)w6%u|l7bDQ_?6D^0ZnPr~p0VN2MiY9Oi0DoB1g~nh&xh@a#k-bl'
    'PrQEM`_m&hJib2eZTDQj-@T05Vng@nFZnA!jfgu9I_!RJ1Qd_q4{q>XyFWOkn#p6N)c)AWS3grWz-NO6DeK#vw2l&-9>$0%B*xQc'
    '9v>a&Lt4H^*V^WE1>f?tBDQPjnA>lC6B)7EUbvjbzSv%iBp&QPd0g0k@;~v4XB_C@PkatNLk>+L+n1Aifv>KWWc_e_-XHhYzGLw*'
    'mFMTM$KA`^Y+Q8<9*^aZUoox?ABN6x<$3>SKeFQe`BR@bs)t=!JZcB%<{FLH_k7*WHRx__V)61+H`m~CD@d=cCuzg!B{|*#8^o*Y'
    'Gr}5upD*SOi<IivU<UGc_O6i;PHg{t@;0^)Rz7RU_N3!oz9%OKzhV1|k^DQAzwC+gfw-6;)HwL9vmo`N29gf1nCs{>GKob4lvXRI'
    'F`lkWA?X-}le+gKVivH`oYV~OLov*rw~<f3<5Mm2Oi8vVc5LQL#2a^|FaGSR2@dv~XKs2PN%!|Pyni5>DBgcMW072PNvBAhVr~zJ'
    '*~4Fzlsr+HwA6vOG5$PXh~l-FXsKhwT?f{qmqFe5jhd$kx6g3Jz2y(D6xgebYgO2Bx2H;e-nrR)Uop8B>GSA8$l($;Y2}Gx`#7gO'
    'o>ypE^2O<hX6$=yO&LOv{Pqgy6-<YI(GfD^#nb1<oDWC5DT;^~M==u@+y3m1w^Lm|voBjd8)a;@H3=L~6ssuuu5#sd^f700A3X_e'
    '(#wy=u%sd0#5ScAA=l`u*)xf_#?uAZ>M@zgGA)JHdCnZuXZ+4R$VwNWrRzm!LViMR(CcRFC>gpKUWQakR&;qnlo88^kkLnpWmd_S'
    'C%fz?M<~<g-EZEH){*1`#lVxd-l#=<d!Wo#<0)mDmfU7UEb1T@)20ky^C(L4chDOz-A&qsT2rd>xK9}4-RtCYQ@6)UKYZn`QRPpd'
    '8^M)P#N~ZWG9D?`u={4S(OF=?1BH2TH)0#pkUmG4#cC!I{`OlqlkObTg=~irUzpgpq023r=cZY`lf~DBpfa;m6szrbj(O%!V70#L'
    '#W2VJ!|90jzH6Oyy7hHp`hU{t7Zi<q(h=)Nd*X<Zw*Ib!ETbdy6{W+<NX3B<-RSBx`5zCpPDJs`yU`;hX?d6|9ZtOK6Q?JiEvZxa'
    'GTZ7md`;hNi}imT`*`(+uMl_jxDl~F=zTV^8<|K^^3!f){tnVQuP3Se{Q8c0fzI8S=YjC)cl`bh$8I@g$dT#Yd<pq+Z@1eNi|_81'
    '?nn+y?(TEg=dwLn5%6>f>3GkqRD#_+rsA2uhAq1%=C*H3krhv$^E8#7qxq-u(7j`qNB6o-tfEIRq~{+Vy@-Au8~xpFVi!Bw{N&@a'
    'r^k@_H*XxWYDeeprb+W+e0+R<n#(%hHqwS1?o8%A^4p~(-hmDlIdno7U3Rd}M6-e6pYmY9=>ubW-zE+pM=zud=jqXlmJxDlw8vFa'
    'Dq*zc*?^;`hC8$;iu)~XydDPpV#x2_J^aYuzFm45a&AC7`rKQ_BYevQ`Dce?I7<3|q{A^`;Eeveop1X72ZK?)Oj-uHbh}(Ls0!)!'
    'Fp92<ZmHWYG5Ce4_~{(eNPcDf*U@|bi=A_PgG#qccCgCnM-Gg_UQiKc)wFikX`?h*HNAMF<E8!g=yPPS=kPQA9Aw$O+xsm$Jywzv'
    '<L0fww~Oy@!mf@Ka%L1gdS@r)UN1bl?$9l(6gf1#+Z}Np{K)3P{>k0$?!9%{UjBsi9iQ+TOW(2e8{>CuA4lJD;I#{*<#VFTrN`6S'
    'WmY8Z0{9yc|H|C-c|MU$+(ImWBDJCq4x!Ae<=1<jDf)FJ%9IlId~e;KL#zVG!L0pMlH>nthY{;nH+xX3zHhkvvpfAfG`!_AVjDHw'
    '?9!9thekf7gxja*^o_(N-rO~YOrSIDR`WX)7mePDeryiesQ7v7L{9%sTtmseUW!|OWY9)3XkEjdCoBH;4RQ9LI%x8+XB3A$yi%^='
    'ISij$6G0RyKa-hzNWI7sW`1q&(05xi9#zvVBhS%k8C3h^F!JkSQZ~B$!w!U8bsM{vIK`Tmh_@a|h0Fs3E>bMi{w7m_L?ZHYK{7rs'
    '2sPF{e0?JjA6q_0-Row&X7?Z~bQVNS#Oh>U-)oea2^&C;)8i-G5vSnV<Ty$J0rlB;_IIE+eM7GXn7<=`@PB(4MP5hgnLFGGS^Nv7'
    'g;9gaimCiN{+;-S?0jlR+WYx^L;AQ`+HbkD&jiN#GBD&pC30jWaj#7-;1kSGcyOT~As1NC)jf<UtQ2BKD(~Ny5Ed3c+Tp++H@9!e'
    'PKW)w-ArPz%T%1GCKGiUyymrqnr`|#SdQ}5FPW?FvW|c2=YI<6tzscjRu7R+S-O>RCB7Kh^Zh94mVXA(O}s$L91#SCTyxWZWBu!{'
    'QjnD;F76R7-1f@8djSruvs}sPA+71M+Az5_?ahWM@=vm4%t*0lMJGCccZ`*PcBG%X$2JO6Sic;rI2(9k|BpUwD{b=i_~^IKYTR5l'
    'eeLcpJFUlk@>}(l`tL*BHk939vy*tv3Njg0xMks^u62JJ-D+aHT_sE%Zxk0&b``*=#velT>i=aMh&h;(wUh`nyZ`W6Clc0_v_7&$'
    'ec?g_;*`dm9kmx}n}jnX$jY^-X0bc^<XP9DkLY&k6UxJ1WMP4wgqGzSDZ}G*DT}lN=7<buM4gv6{(*VPI+NR!@4gBa<eZi+t$eyj'
    '(<w?!;6HyvkI}zMuw^22cYx(Xp_M}Wvm4a;D+<n~^T~F!Q+o9#zBt<>tC6%)WJ<O+Ge?uDBweqQ{z$s!FC*(H(z&C}&(-BoHY={I'
    'B8N&&B~nSXHyB;*N8E%#;B#zxls4yF1@bNIefU$>R<Z)>G2A~H4zXx7yFh?<bLrHy9{WC<*PyuU@G=j1yUXNMf!T(Pxq-7(mq^)@'
    '$-0jR7_TK(4`Zvm%$>aF6t#8DrL6X<NPC~t#5@c!^3ls=>r*l{8WkDKU)$e0;hfH*W=i|yJ*nlX&$!xHRd;bp3QsNMx1p-;+rdR>'
    'yd0G1&<QHm!w6&B*wLhluJ_QwlJrWCX~!0%C83I<(%rn5EV=idm>Soa9rWrMa)Rkx*L^&!MFWt-NeDw#z4>EROt4wqu$sMKTr1tw'
    'O{o?mpgq}^UoeMMFZAs^2jJKw(mN<Wdg0WtcRgY3S1_P~5JX;l^UW?p+|YP@MN^LQ^bgQwd@JS!o`(k6DMG6``u?(`^t=jKr2uW4'
    'ceBe}$*)N2>-M4X&4J8-ew5+<h17xr#1+o4eFyseX9~Zc@9+ieBX~Y3hqk}<^I_F4vM3VXt|R5%`z2K+Eqtu6bo%_v+91R$rLL0g'
    'h4Ob!O{PrAy*_1%rSWm(4-g}|f-n7}XkhF?qI}j1<FkUhZrCtGZ+*DV{^-Y8(id8iC0bi@Hj<E-)1-uM5ors3$Rwyjc2j2W5xSf='
    '2v9}!A!d<DGhe96x26Nx8-5xGLr5LiH=CYY0nW{(yNYo32N*``!k*@^g7kxliWe!fUuKmiwF3%Yb-{QG9ewBa&m%N+SAK_00k?#I'
    'Zs+LXp?>Spvx!jUp<`fP)Q_ZWX43rU(6N8c47yB~@winKF&d`lR75dUOQ}J_%tCbGiP83Cj@z&2&70@3frsiV7Q__1T|frq-<T7`'
    'y-7UKVWQ5Y;P`5oH!}-e%PlK-^6H=!nO6^K45t?6pIZ<FgKf9R6-3YA?(YR`T_vj6eoyFa+_%+y<wN%tFFgtF7bQ5ceIS2-b-Q?Y'
    'c!a1u7>4yJ5U@PmJMluNRpAOfp<)vr(9j7UB_ys@x<ky8=P*fOt{^pdK(IpliV3xFWn|v%xxwJ3T=7ozlFB<}FXkt&HzU49tIwzQ'
    'XvEXXj_1XfmchoT^gULq;Pr?LF#Bg1N2lrKPOyknfiudm%(=H=IH`6^^?t5UZ1rSwI%pfY3&6g7bS!M5W%=)~6{1Id9iGWx8L-(J'
    'rbaQ*TKkrVw6drkkI?-0OBJ<>UbuO|hygH{KF*eEYHzzGboLA=09a3|r9SR;Q0u+|`VwcjyPD#37r5J2_sDHO%pyZW^WUvhlKvt2'
    'k-bPGP1MZrf~s?2F!>r5E`UL#8JzkG!babNTVz&3`Wl{Sp&IYhSeWodg5QFaWJfY5uJB1SG%S{8e+HOAfcbzc`!gWC3|5NRXA?4q'
    'n~xmFKXN3BE=ThVPFa2Z7Q$vw#5b#mFRX9gLg;ivgo>`m@(WHf8@A(w$5P=Q+3Lm3vhf7AS&DFD6fp5{XBKGCJ_uqKGcSPVo>|(P'
    '%q6AtEj+*3u1xJM>vlo#W(hq$=|~ra!3C<HPftBxomjtCZ`rC1BVF=0qZ<=b-YOoj;Cu7Eyqdx9+`-31chNBBU+}LI_rzh=v$(j&'
    'lb8as-m6t~r8PKznSOJK=9pJ;jjoq<n@RJ4m<z`Sck&}<@ioiFw<c4x<z3=Pl{hkYHz8f3N#)n1^;2?i5+NIpkda47{Rpz^AnEdE'
    'jca66VwF~=?7f6Dt>a%IdEdHI)*-vVJ=F=Ry@=bqZ5F>wO$}P<Dh7aM@WcX&54k+3gtUQGT5jCk2z4H$Fb?7EYcij?IyHw)qyg+C'
    'Vuss~bnv1w=nJ_FZRt`!!Q8AiQR0gc!4_HXd41cgfUdL=Id<&Qyu8v?*+M)D?OCJ3t6XPZ12@x+pEDygw*x<?A$apfBe=#6O$&zc'
    '?Bv35blMp4G%wS?4~q>-*tY(oZZIjOLPS>f^?K4@aL+@QXP(qrC|Pqw!)A%>Jc_#<o^HV?rIa0OqFJy=-+;WFhl6-^Ue(J*R<sc_'
    'Yi%gpHfJ5Oyba&;o^^!_yipE<d80Bs<_$ME#!tQv?)dX%&*3t=U{TZ(3$gBRBD*r(CX%XR#sXObcu_6koVF&<VTWdw5(^2}6&mw|'
    'BQ3>K^?SCt3&(2~KW?}uq`!YoZtzbE9Kf_)zeLgZTQV=dCLOzHhm`%Kav{^DkfZ77qKBcO?tRe=-FEB|aCgWlY`~ILxl@{x<+<jn'
    'CY5qi-v#96hpjCu+-o?j`oo4W991E1!-fr4K6A3H@n`<HiJQuFwdVP9H@>xhxEr`G@k??L+Kz!2>s0Tp6)QgE-fzsWWOjzqR@T~#'
    'Vc6LE87?SUYmm<0hK+4PA@@?GPjx*fy&`J`n~eouGhyT};Bc~*OQO1k(8q5f%Kmfj>+^f|-a888xuGgA+vWwi^pNg3<%TkJ*bLXX'
    'l6DY@%>(c~S($nnn`>X5Ax}^7=Elsj+R?n(71rv?@}^~Wb|B$Ra-LFSp*ap(^Cr4%)Mc;pfzXJDp1iRs^$BmRp_~zGthGxH;tetz'
    'rtyYt;v3!|GeKzBB;Ygjxu2W&7~ju0NZYwJ0UdC&RkbK5lA*5P&V4^N!;iu|9S3Ws@tjl>V7VLjsMrF-?K0F~P(CX?*NKeMW$fJY'
    'QHSbhxBGcnes03rNj_hL4dU#>RDR;4>IZdr!yoEZh3M%s4nYt<Ir~B-ldIOaK}fHAIeCv!93KN|ztP^$Bqg#6>R|5+%J$*D8e3q@'
    'H14AMBm6Rfx5mTr?)>OR7;T%ZqNu)fipqtqvc%QP->@ef9;}6TQ$$BwF$rgt{EP*HYNP+#yxqLJ1uw@6Gh}%j^cK3;8+J=;WG6qm'
    '>_bsY0h1(l;E$nrrfniTP)}r|`7iFnw?eBUgeghQ(;wAIXR8vk=)8GD)@C0fwZ&osF50vKJgxC+0QLRJNOu}7^Hqz-tHg`M{tlEH'
    'knA^S>H&HevzgDb3f^pW76SqUf0#9^D0|kd;j+wce{0{G&4?c0`Ij0ESe)D-*lbmlY>NSr-_y4eyz)Fm*%FJnuL_b6m80En%(%aa'
    'lUSOvhgw%x?Oj4jYW(OtQkNhDktLr>8N2;D$~u<U?ILlEDfEBSfO|YogAKqqn~J(@!SVG0bKrejXh|#zFjnO@R6j~3siv$>RcZpA'
    '4CBa;+9%g2gXu-7=`OP8_0AOfUS|-qtjFZp@o`Xf3Hp=WP}!<yHiZFa^DQuk&PeEBQLys8A0u?PwD#nQFAD&)*B}@Do0j{ZKf|Rp'
    '26UxR9-uSPJ|W$i+|V^AtI#jJcHzBB`Qd1w{{_N%<~!R|Vb-?;$Y9~wL3vA<PxvHQZWdHjk2t5r+mX(2g;J5xEcaLU)vRRRb!hIG'
    '7D~~E?hIz0>`Z>s&=q1Gcit(Nu`J^>J5<aRri=i=0O2XHHJ@yV^w5zq?F;i+qBzRzF!fJ^0<@$M^FZ~NJYxrwnHm-bA<ty~T-}%_'
    'zzm|loY!?9zs?rSZ1zPr__eupHx!cp{KtmYHte?nw+PvljCiRW`HFVYUPtFi3}vm((?MURv7tg@b1Ke^jQ~2~x`HPu{rSJf-N6&j'
    'XKwP2%pSQT138^<bTzg`Qqq3mCaF&`b0tlGIt$N}l?n8X4c1ip(@GtuWqkYMC(8OMPRH95o4^&H{ndal)jKLQR@DZ6<)dprl+I3y'
    'pDBfPIFVLVNQJ89lo?w>_v>Nz$SBxgU-?nN<3|3eon3i!0Wq=Pne)b-?(-K8Ov`a{MYr*7;O2@E%L`z%D?Gy#nLW!v;Vh4g4ExG('
    ';!s}1H-voQla;*3uEfU=Zu8Zf26DcBCXC~*=PY#9Ddl6IDe6O{sb6;7VP`=KvM#oFkIMC=`!cGJeU}!2^-x@Yufci-`qJM4>tXmk'
    '2CQ8R6Z)(y02?wiHhaq@irAX^<$Rb(ZxYdL4YU|SSF^R|H(n9r+F)2-wQ5z@l4;>x=I8xLS_kAN{GueSq6<7Ic^%+F9s(~sJiKlw'
    'G%rP)Oix$*qhECHUN3MgTae_wv=D5DA;pw+Z8%Q(Xs|A?PVB$3kUq+=*zE1MF|9A<NP;qnUEGIn#^{bxS{S5C*jLiT*q;~nXI5v$'
    ';yXz4oTE-ty22|=l~>UfE+W@olb!#Gy_I__>6)MVqqCXfSW9;?g)RH~#~&{A!*LeHQeUdyHYa~Dd5D|#cicD1xn@rH4`W~3BOD5_'
    '?42tFG|^n==WPcMwlA6bp~N3`R{mERcJIs&s`h){<BB*qYfr+P^+#YUZNH$$B1jpyL2!`lsX%VdbWs;R+pY|r!eA%<rNJgOFQue-'
    '*CKZBQ-=)8dSl~(FMk{KoQYU=4vh1_$?+R}WA{E~z^I&8mZX+<TJo97^nS;7=e+4l@26TcI0F~h3ygC!Twpt(rz@!G0?VXh<9#?U'
    'vWIMP7>+sV8<o5FGB}pWPjp{W1U5s3NjY6UDd~DCSD4Uu1x`x3UUuFR)|*f9eP!5lDTEHjm07NswapdtD6)I$KgjnH1@XU_)zBSo'
    'F+bbA5d@7!pT?<)0M97vq^LVnx4Td3lI9-T_2$3EsT20vlX;ki^L8MwXYAUb@KtkjQh+f2L7$kU=k_f@mgl{%-ULxBMF1xEeqddX'
    '(qFR=U~QY5KlS${iU5YiXD&SoPLC+FO(Jt_f1*gIJ{76TYP>0{Mmgo1`L@sF%`n6EBu3F3RLQ{nHqY|%N(pyJi6W><4i(st6Io`x'
    ')JdaBq%X3C^)^4gaL5_;x3yu^i?uUi-B^jp_@laSn!u4<Bw@!23T+js1=qOd#}6+$8xh|u(gltZ#m&6>(Qh57Y@3>;Y0Gm=u(aJx'
    '3PVuEXB`&na5uLm<*9p<TB?UiZ<atK)7qW#HFaSxF;9F#=Tdu&6szp_MuCd2xoQ^p;-ALDN4^)b1dU=TqbdxGV+r*86u$n7D^OU;'
    'GRGc0j<X<z2Kj-M8e50v)MClpMlpFPtXHpIW;`~)no3@Uk0{%4wIOA}h9K(pz}UI|#K{{PkU$)Y4xxFJb@~BqAnfR1Jg+NUX-t&#'
    'x8{_O`>TIGYHtft?+k_p^h6s<H++_^IDe~XeVkDkjwYouBfh3X`jc=J&uefR`q1BAv>@NUS3O=jXnmQ%(?{=)DR}(pinx|LQ?mA3'
    'p+#fXlw^9lQ+Zr-bxYt|eG;YA7--BYc_pzlyIABM&iSk7c?^FXY=-(&?W?XtxhLngbAKPpEo<C;%(tvD`#t?`>CeO=WO|W`@*;BF'
    'w_MDpn8QmfDX;x5KRzNt6+?Nr20H&X0h(%*#5<TRrGw>sHeIa-cgh}*rSrp`zRxXV-ogson$HUEfAJ)x6>~~w0*=jFZ>Bn15MuvN'
    'T=%b&dgp9zF>_-{y(fnAWJBe$*{~jak0!mAIgRx_`^&W4F)@T}O{rEpuf0UkKJ`Z&pTF+EijK>mW1XLVtgZLG`MZR`6*>(@{3-5<'
    'n0(;x;W5qxhc)PdTiZVf%IP8B{$S3XnL?DgR-`=Bon8LqX=u1{MT5iGJw*Au%crlmYndXP_AAAu31tl};Zbi&aqQudhf(SJKi<qC'
    'xCgAIyT?7y+U0(Zc+!>cGq6lTnZIxqmw=4PSgEeaZV5o4t+Ri|kMhGipc54VCXimJ;4t`7!ZRWFR&}x;b}Ut0waO3S!MvK>6IjdO'
    '6t~lAa_L}L7xB#ZLHW#TG6Js6%l0RVWyyKI^^Fzlf85u3vUU$yBni1EtNGWK3htHlnYe&w1tLP7x_lvV?P+#j9(-4e*Luw4Nbdt}'
    '3N-_t=&Lwh)R!bio#HQ2f>*I<$~cy(lj~4G%qWMluMj?n$(6*Zt<+#xBHuoWH3(6JmCXN_#ULRJ5tQm`F8@sFn`V!5@9`)d%LID2'
    'Hw-h^VGmb9g1+VWy7}Y0fQI~MUt<+Gw88<4Ct?ekMMrnhSH4l?vBD`B^xa(wCS%F|b3m#taf;vP8RUu9j1_>cnB=%vq7mZ|8TDSO'
    'ucFtSD~<%b_kVut2St`_$i&dXMSO<5km}o?V9QHcAQk~6A&h|31rX|Dn-?<o3J=H={LSmKv=4O91EpXsl^I(FhnPaoaC6$I(P#j4'
    '8n&Y!j(lBAW_B5Hk>+!AW}JO5MQ0UQut{)M0Ps={<Q-Ranz{?+0qEtm>?U}ZD!fqZ&n)8<UrJhQ76Ioaq5xKBf=)4UvK(Vfy;3C='
    '(tN?RCUn-<mIh-m8w{1;J6fORO{a_Lxxu(Eg1Y1n0FAc2$OqNChx;b;`~lkm(qDrQ`mZpCWf#Czd-@a0nMDlHK!?>H*){wbU^YOq'
    'aMAS)@GD>@I0kTTf_+<np>9gqZCOCvD<3_;PRRd!LdtIYqd1&?VujnqVnxOxu^L!gKk+2V#j1sn`9I!5|Fp|O5Ykun_(~+Clwa-A'
    'S{#oOg=qIBVWH9hQItaGWthfB09a^QQn@fzEfN9!0Aef<kT%g40kz(OrYqqV_57QG;8y^tOoM0DW2JXQrWWFF&2;?p?}aov7Ozgf'
    ')kntpsCBY(!lZivr0j?SkOCU5Um3*3TYdz}1XtC9R^*<x!b^Gb0E*6WMLq)%oa(yj)CT$Am+>qPUSbh@r#NY;@@*%uS$hD4d3_uL'
    'l%`HN2*3hz20=~@!)K<1CZ35~OlMgkU9561Z9RD>pR?DaxCzBPvn)PfmP~xiFEBr0a&aEvn*vDQ63J@v*3Cz^fO>~w3p4J>3POK*'
    'DzPZ-MlaMwqFK3p9%TIXN+O2xZ6(Cm6SEl1$?RGvC9s#7r#0HPoW3|9Cs(X~u3Z$n>O5W<{Geg^Q`~mLa|>o|fR9Wh1j7JuDwC-i'
    '5d8@|DBUwSUOGXbrE`GQh&rUNKg_qYaGMjcPPCJbXhHyk>~5nWLnxzc7L5fI%F)M^huc=k(&wYbf!Y}^We4QH@)L6=G9B-+k45P|'
    '{p3D$11`iB6uduEoGrDXOikgXI{@;0uY&6luq^4AyV@x9Rgp%qjXAHUe%8nf9{3P+z#NT6!k*yW&|l2GC)*-;`K{jtr#<<$io#N='
    'jG&0<s+rND(wMo9_N8!5ab9l(LrMF~6Mem0?jT^dGM#%6A<O6JmV}(!7wqlSdqexa1^KsBmIXc&AeXP*Qgm7CI+MX_L^Hivo&hmn'
    'c{8vY2&6j}@79cC{EvV?kU?Uxac$Tgmu>@y<xAC0k3Sp4GxRD|lCuZ>7*u`DYuAf-6$@ku-m|34b7mY8y+wY*>XPD@4h(BQ7Yeew'
    ';2j>YFxQ$J3xFL95$JB!dzeu+<hnmy(7Fq?S+(((?t&*p+h6a-<!Ex=U0H~s@^=NlD;aMmv2=P)PGaCBzD;7+BrffL5_8r>oWJI)'
    'G=kEh<Q>TWhP$~?G(AM*47l$X@|+;Jp(@`2=0OsP>u-7~f!9g5%m>WvFNq60HNqg;5{kKC648$$Z!1-M#sYVdyt!82Tuz%Yyg5z('
    'vjO^xHNso)3Sq2xeO;0H2N);?{Bti+iZI?tT_*#j2g2mdk}{-3puViNlaDwg^r=@AB^nIhS$&F?RP`cpjk*=UHBs^NJ-|az({Wo8'
    'eK2{lFj7SEmQF3<r+f8`!*JTXqJO+Rz7QPoNgD~4P5tAg=miWcPQHvcDcKP7SzzV)HM|+CKOt2wcBv(?t0c?sFG*cF<^q}qkrwU;'
    'F=xFQz1bVy^&WauNipj0(!)Qp7l-7!gE&x2M52AZp)s`swUk7oVOus#l=W5eyPZ`3L>w^jcRAmps_5iK+1_KeFTkx!A}}YWp*Reo'
    'H(?XSW4edfZ?jg*9wSmqI5L9!YAc#8@GHW#yl)WWHisZyd3F`HVTFPR=KP`utV6)9dy25qPpT&qN4#yt2O5?TxZzjqacRdaJWO}}'
    'KW+16<<I`RK*lxdOPd6h?!~rHIL8|n|5aT*5cc!GKEke-bKWg6XE}G->bu0sby8lj5Pi~6m<kbiR=UuB<%*J2I%TbQKz0WzbbWva'
    'h)q|X7En>3R5eZBJRHck1OLdZm>QS%n-%RM_gX{U7GMdoZ$yR9)VPe@5`V8uk_5-EAxA7pyq}kWM1qhm;0$D)(k&&SQw;90$r0)$'
    'AyQ5f5yUwVT^}7(&|YYcgg8+xa!tw=?_4BRDj6>l3qtNnJasv(h&Cw=c_kiyB$4B)AcZ~5(<@nm#oBWy2UnHr49DL~R>gSMm$ZM6'
    'C=I(wU!{=hMoC$QBu8XTig*anP|m;9rn?sk&LnUOkO(~gcX=GvmW0=m+a>&hd4^E>%jBIEqKhn*azJg4NyO=f>tGFV^%&z}M3Rb*'
    'DVPRF%N>QdF72iWSSsYlIWPW%g^e_1G6I05K#P%~LERjb;*vS2m7HiYW!y>NbGEEb$hG4yaz~h763ZJ<29*^ZWt5-3$_A)TW{+=1'
    'sYHqs@~0X>zw7dZ3UAlw5K6+e#gvEX`B6I!q}0wY4eFy+H~}C7Sj^4=IiPMh6lKT({jdMve9+)0M0n)?n}C{gwt6A24mb9#@DSM!'
    'abrrZp*!wJXB4Fe?Gp9>lwA%zeG~E4X<Gq+lfEIoYwkP!A<tZL_U^y{e%u)wM2+v7!Gh*pmXwGwUcl#xwAC^$0FQhK$TKKi0Es>2'
    'ubk5RELmb3Gb(VZ-3*xwl}yWl<w(-n%f9#5KvZqn_ugu_TS~4WD1<#0vhUqgy1DWh+9ns`q|D|=?FF1KCuN@pD5sqW{+OpueY&Hy'
    'UNm}gn#nzfEjR!Le=-R`kf-g1^opo!*Elo4ZXzvxd|)fjPWmAnBkS=G2<R^Z;L_Js)_=D}_EAc*W?iuldZ>g;kpe8sQ|Mwl>3p{2'
    'vTl8^A12%CqmdhZCfAmf!?k+NNPQ!wBIMf?p=W1&<Z3#~XI|3^0w2?cHbqLo$%{jhAU7O?(^xv74CaX}Kpad5Ip6R2Efh@Nuz_f|'
    '?$WD|xtgqq6GIG({naf5kjEJ+{J;<}4h#Wh(~SV9;H?4RTX?Zj4zPQtYrS3$*i7-}Z!$nLO`;Q<76L%|9JL@az-(60O%JG=r>bcH'
    'xXu-I5@0AqSjqvVl3*QUq;60^aIdbMBFO5(lMSB*NZUT60s2b-Pg!EWKMgqJDQpu2Kodje<(~m~KS@^S#$KIKS_Bl`KYlfnb|Zsx'
    '{&l;dGNHs7km$UyT+_iw4|W_oUseWKE|edXwz<H|i0phW)Ba$W4)8i8IL85V$J2>2n)5ulg6?V~T*nn(;tI}f7yi?tXI>Yu7Y`WQ'
    '(scE?(D)op)~iF`>NQDr)9+=dQzFmL6CSTEMeUgv1B%3Qo9(HD`MMk{>dOF5AH_<Xhxra=bYA*>5(8M_(D0~?nw~XS)PzjH7Jp$7'
    'VuXxvk$j*K$7Rm+O;9IY8^XF8C7W{BtOY<)d*>32zM$qIi1X4+@&vUjvV8z7#&t5DGL+@!=Rs=UB47b}<Z^8!cS~6=5SnJ(ixtqf'
    'gLMQ$;QAt<y<m>KE|?c$Ed-T;t_!gY1yNUGL5XX@xiE@>MVkTXa_n6}&dZ%VqhCeCG?vDI?Z$w{2q+S#`U^ItDuSQL?Yw6bp`sKL'
    'GY&G4^EUrN2wXOQ16vJd^cYboBeJp4f~sBIM#-!HA>MfnDF(=KIDkPe5VLU58KjXLVzkc9UP|^{N#~Lvr=N;Y(S9u1)IclewK2b;'
    'oWir%4mkx!UOG;02tehmp`NY9-dEY`B%jHmh`y1stS_%qJRen0;Q8rFv0#;aVsY?nkv4rVC^F{>wq3SdagN;+sVIsR$U(m)LR!Wq'
    '!jyi&jfE^cf;>b^6Jdb`fc`Z$c_L#}gI+$VWtjtdOLzq@A(TkeJO51is?d9MC3<thxD8k}pjs5nJVx4MSb`;Yv}ZH{x$*#MuGc|B'
    'p1_zj<;70OJGwhBspdxU4&D~Enuvo|iVFzWSUx4}WzzY0RD8#m3tc$z^fle{Mz|+ODGpPwe^3>r2ksE96iN@Tclo)mcZ+#UD<a!)'
    'mkywo>!0lC)Ib+nECDx3d<z97SS?V<a3s9zPeoPMRC-07*!4?%F*<{o9CIhvzFUE)m}ls-41e0Ef`x*aT5$x6Tm>B@Vy8;TuUsun'
    'N-#MJdBslnSh_;~DwqJ{y5>br!TWP}B%W5XaT&2JIQ#_`hLe*O`fIR{`(N9t1(vo4aA6S<Om1lg_)Tzq6tHLyh^faMnrQdT1udKI'
    '>1itQ>vr>1>ALV@WJ*zP*v>EY{Ag&-b*_gloh?oUOu9^wl9>^dbPLP9QT1O^5_As9xmH<!H~&9*w~jAze7I@O5eNSnYqny;ZDj<d'
    '=jPt7@vrpJY(sL|F&7a#(N3C)8fZaPTn>Fzc=a+;@-Rq_7)~JNET1T*=O@Eef{$F?rw}Kgp&oa~Sed+a$J<7LcDF%e0BA!+@*;VP'
    'la^ElR`0DQ^G3N0P`JB_OmR=;{K8!_{=CsS9Te=Ss0UO!qXX5p@<xa|-Kg4j#gkf4Z7pXAY~Y1ItzZajM3J1q4H!D{rof#>K?N<Y'
    '8TF0f3i^zN#zwYwcZ^2D<am908*a#rYD|MF^fK7K{f9NDf36diJq)&f|9*{buN~!$K_2v78wPii+7uz@Zz^jD?C}5~Z@p1n@~{0V'
    'j#}ev2<%GfS@x=uhQLmg`N~>u6v^G5qO^=9Mje_>N5|Y?M%<!vbfFB;f&MIWsmzDABgMa2D`gk&>`PhVUu5EW*L$@0zsg)+Yx?6e'
    'mif#`^xj$iZ;teYJx^kDsHDD4G+I;S{P@g0EN-z|DFBd7_%f3fxMP55$?m0Qt5499qJ^AS1)bhfR5}7Ik}pm$;%s_=k=b~+5k2Zv'
    'sJA0gwA#-bDQH3!1Bn}+){u*~nWy{6g6Lav9!6$1*FqH|3wD9oACJ-Z?=tq=$-cM3PRM;nrhz0$2p9v;FyLLszRx^pZvwY>SbP0l'
    'R#C>=JL`HD%V}3)4wYDP0?r@19E|lse=_W*M-mk5`ijF!jE$sZN;XT(_fkefhTE*E2=PLi>K0c)H`DN5honj@OvN_QxGO23Z6K*z'
    'cAIeY5Z<e62E=hLRndEYP@1|hIgm>w_e6aM=Nh_(P@Jk0M3S;p?qkOKJb|}fs4bZ9%KR5_`d9#W9~>(%?{k^Q0iln~(g2jg$aQWn'
    'MO|zs9lTR=){2?5Y6Exdr%yno3&nG8RO~H!IrQh#x*WIBb`=<=UqEp4*~ZH~H02L~C3IZ`B{!l$<y#&+*qKk#Clp`Oxo4gy2+JN&'
    ')KuV0Q38nL4i?P><wJ=`K|SA;_mFaW7`BLv@Ev-Qv!chUBLJpgLS^`wag2kDYSRC)TB<o3iM842y_g<!6Gz*3^tynJ{M9T;&3`yr'
    'QTAbB#*>Y5Kb$%`NU-~Z$$wPuxL|5?`6yNmm1M3Ja_`ipnV?%Lo7pX%7EO?!UH>&e_zxTdx(vRei!n-SWxWJFRw8{aKZwym(){Ap'
    'Tx<vI4@_0(zJ0L%8<RW?<8T)i16!o9fh-2^C*;mIhF^lG2scjVR<<anEz=en8Bc$vQpOurZpsiIN|D<tFjgj!<~RZBfsx)4@!JGJ'
    'lsCYmR%wN$*iH1V2ZC(MM2GTPQRXM2V}rYB!3QZ71)cMnR0~nArc2D$K$WB4Mu_lmc<9eJ=J_J>I;}-V2VoNGs))E;LiJWm!^mCl'
    'tTUmOOh<)}px_!lnRC}yAW14W4ZNM1I^}ml8ZObofw8Rw5xeVjRANBRoZ4P;-JZ4d44$*}&r_8B_U^A-2y*>y9=l+)f51yt&nZB_'
    'nd~w+_T`v|WU!ebl-mM$y(Jlxp!Sw09Fjxdvw9LnP^AjFtBOWYR=i=eVIRtm!nwL$DT4~zO)>6}L!<ruAESFj?%6g*PeJM+_RuXi'
    '?wJjH`oTs}E^0nAhIVH!*U|{erazQ4f->Q~P+{u2ca5&g%R3nL!D5pj8N2pdz@q7+eZ0?IL1Sa#YNeEjN7z#D%-54TrKOF%lXDqo'
    '3!|0lFmm_vxZI-bcMlHF?qnm;wGAlXLHM1kPgQ!~98w>>+EgnUQ)SujspzI(4mF55UrCysm~7EbOSf^d^`;^MRgfG^IQ7#=icoGP'
    '7p=El+2z<G>0JyZF|G-Ui;&Ec4aITyVD_FArv2)Q%Pd^W2{y&xOy6S6EFo`^WxAjIxi-mr9>G=!(@B1`kmISIlJN^<)~AJn5#13r'
    'D+PL&$FsspBjwTQO}&n>{N`W#=<&32Hoh8dkoN_DRDH$hEnt@Yw>|xkSCkp;^V<*gC8G@A^5S0{oG8i<W!&dRu$dMR&K|Jvu&ay)'
    'vUzFN@&vLhNga*gC^jMb$gEuqj^tO;rOV-tDm?~~!}%y4C=UNwPp}N&jEClx4-DYV^smnVUR$bKW(cnVf(hLS&d3r}Dh6-ErkQOq'
    'IQLdB-p_e@;$r~6VtO20k@F8KK5pnvplWOkuZeoAd}ai6ai5QzA;jLhemfc|VZfKf=)HqB{n2^@60fwdvbA?8Azw7pi`8vH6?|EV'
    'V)*+%cpMy)2?fTu7Pm~3(5EJ$$4x@JEiwf)!1o;5aI`7tK`;e<X#^EFLugzuZW@zU2s8=xGzqQL$rO~KI%_i%(5^feh7oiLH!~SQ'
    'Z*YGYL#Q$fs**C_2^7Phy`mRy@&TMpyiIfyDGuEsf5QP!Uc62$;+~fVcN%K~*3|^8x(S%MX2+-A>t|r6W*39m>-H6cwSj#m-tj&o'
    'PQl;*B^3W{BNH$Sb#WM(-S5x!`LDrj-R81)cW3@k$+p<q)I1fYQK#j%qS7>Z$uBSb@~vFD9{CD!Q}~^0PtjhkmZF565V@*WFs+3}'
    '=i^$@1D9B#?@vw}y^b<HSFVwe$3ouA)q85dTe(dBd#>I#Y-na`;4V3z7}<X0jv@w%c>SU<P35^$k|{dR%wQ%dy(r!Yw7!WnuKt)B'
    'Q%3D=+-5SK=Jkx`bfB11QZGZVhLe)DK<08NJJOP|;pQfea1Wl@rjFR7_lN2m6GuqN>qwH<FcpV#x%>!GeE*Kq{)+*OaKD=>)31E9'
    '>3)JrlO6xWYxTgI#(2Gnm^qMbRm=8U7{dgc={@KORT{XIxfWgi=^Kk;a}}qHXcznsK4Q3e7-I<Bvi^5GY4Ibj9>Uw6@hyGZl?N>m'
    '-gbA(PtOp(fI$%8TaDet<jG$~Hju32BHH+0{H4t};ju?GB!&YbXyHVeTfmdURxnoAb3}D%S*C(M%;A3pppG$s$qp?>NC1^N_a9-_'
    'fILZivX)hruK`l{!CH(CvqAH)w?cF|d3zW23a11D*XLGDdQo=7{`STB)aKlCifvwcUiH>b-5JJj^s@?5Ru8XTd{x+Z!`nKhsB*~w'
    '2rg%eURMZ(yN;$PdF^*_#>y0pZ;=8!%uG@LZaK#KIpN5lLeO?Gb!0M<-lX!ykGv4bnR&4zkj^VEZz^`=ZC(3UVC+ID_N_j14wO4&'
    'O3%X$Wg)gE#$Y!XdWPzcSTS9mo}ZA7X!T4cV>C7K7I?wSHziHrGw#%eb4BEP@62*%=1+5m>EP7JGO`)M6H8P`=HDjBWFlYvBbIUJ'
    '^TucPfcl^1;r>7LQ_zLqnSfU3aZE<gpLqCFF&Sr2aj1O(bd=t82-Y~dax)-8g(%3BjN_<>ek1Ga1qo${NCLd|N2~En7`Hjz;Oj@L'
    '$KIRyPp62F&9t5yr4D96qQPP2nxA1OJ!<$VgTsUG$evFT1rtsh9%hq2OfUyRx~<V+GjvsjE`sODI%0H~nQ6JtO#{$WE_S#i3;sm6'
    'j=h-N)A%r7%D)ogoR4B?vBO^=AkBu%XXd|Rhnc$-j5UvA>fhpr*|WVE%#~xs5A$bB;JW|fhxxOC%H<P>*|P~M7ZZn>TcHqEV(Rc0'
    '+z|Dt!}x4{j1IGTd1YD;d!`49Ms#1vV*#6AcPUdXPQ^~lbT&<ozxY%fEi`@<UpC*yI`^5)auTR`Umd=kb^~6`>04T~A3%hiB$pqQ'
    '*%d&_o+5)kVh6r22A^_>X$0#RgWECc5N2x(Ck^z&YXIlw6lVD`grmbHl``uTgWH8OBZIXuoP3eb87X5p_j!jw#o+uFS!;^H`7JcX'
    ';KD76!-ZQEhx51{6L5A56L8WnpTnK|&ZS(#3^$2y7|Y?}dv})^9S`b%USr0Y@T9`r*rz)N8JPcSo}*~0DB#ouRNE%a(;FH4qRjF;'
    'bE0U09D%Rs4bmEQieeF<QiwtQc_^19nrJd5$BY3|qz4}beGV}t66tJ4hy#qwdkm$bAD~U4=!`3DOoBKid5Fo}P*|n$w~`KCrXpwI'
    'Q+XnrA(!RdMK`md#z*>z7wG|F6qMZ0CkNd)*b$j`%w*AqXr3!ZaLGA~qY_6sT5e7hy*AtpD|a(ZK|148Syk_xQU<mML8DnKLpG!?'
    'D7*WJ@2(As69?D;wFpD!0KIpP%l-lYwcpV*XdC!A(}0t7op}6JQeobQr#n0>i*d#3jHt_tSwOHz>SFv~u%&ycoStse>1y!<$|>($'
    '<S-$AY`-ClIkse58o<mY4UQg0FjkkPveCm>0s$5nr-!k5k*qL)F~YM=eqWmfXncs(_b<jjm`PTFwG1SBP3FtPedN}{DJJ-o|7w`1'
    '+4KE`X3yO4_y0+2e)1>R{OM1w`FDS3&0BwR&0Dd|FDBN!T2k{Fuld)XT=QO^T=Oj3Odk_#o{tXt))=pO!3CgZrtz8&5Z^d@V$0XO'
    'uijy<?C*v8HJ>=$V9l4Gd@4Md+3dwc4+fhvW1VuFnK;yl=`#}>m^k#Unq`0+Z9$5uRliB)%vM(G;`f^MD53EEy^St%4!j^O!h5mg'
    'g`-D3{y{9f>~?JvYo$FJuF~t9SVWA^3^292!sLo$`GHGvE3KCS0|)vr3Hbr0^6gsufCU<+3!RD|7%$@l^apGkuS2{SRobMfNq4fe'
    ';gi!L$u-D0CA$=h4-B;~et^Za$usdty{eTjIlUWomvPHUWs4tBGS{A~CPufRS`4Q#9xJATRyCAiw!2JgOf1<8c|E_UMQbC)OiPWZ'
    'MMQ)#$}1{MlleaI=mMTaq8(in84oY|WsCVO>g9oE8eY+AbTWsW)jRJjXArY|J(BIpAf+YSG40q3<VG+iRX53CIx|J*vma&Zn{C3J'
    'z1ZJU=GVoyk23{WqqoxYh^~eXYqBL1f{2UlN8i#Ir5U4_oBj@jbUS+2u7eyAw$JS>8SCjtrlKe5JUO@d3L*MzMHkte>jX)nzau*7'
    'cVYggv7^~ssriUws5VG2^L<a8ey#)EHil_kM{K_xldVxD_^x6KuSF(gW>~cdwC|qWxqg{F@mrs}{z0)?gz_iaq1U7gLueOcXh($B'
    'F^1MesGTv?8dg~d;)@JQ>?BMshw8Wg55+Yzd@&OYpDr9G!^*N3nX5;h`n5M$WI3$AofFG6ACtS`+$iZb<1Rd()|G1#^cij#Hz~OL'
    '{(m@cc<Wu-xNnM(oD^Ml#Z*27Gds)?wLW5?lW<uf8l^g-3Y8d{QD2)U)-1&=J@A+_Efrtty`}6KuFlvpxW|wkIq*d9wPe3nE4}5D'
    '^2C9p`qG;p@`_TPY!(yy9h8|p*_OzQRMnlu8evmJvfX}m3S9ZVJdc@#cs-9=K~u=OR$65^K1;=HotO?y$R~~jCQfuzYOE&*jFk!%'
    'Pw|s;RabaC8E*ZVD-!oas;teCcq8R|kP;!Sl4pQpK6Z($QpiV;C4w%MC;D>s(|1hL0zGBw#u0KjUo~w=bzQ2V*X?a?eO(JiRn=Lf'
    'X;IZAosk*aj5)#vi79mDPO?T~zi6dr{J@9eHQq7A9F`Pk+v-w0Ut}r*;wDHLLycYDx*756pwAm6ZL2tRQI+w`NAc~fo<{!16+ITE'
    '!;`TUh4+*p8a~Y4i<zrPNe$PMS!c>^485tmXDM?1c{cjBb3w*$3+w9yoRc~H6_(PgX!-m#&k$dnlFi?VvWH?CvrbS{Qcma@A8E;L'
    '0K2%4+HFIbthy+TP<|d)WTZ@%ixFSKeK?RT=sao*4q|LuEr=Hl0GhB~gyO3X)Q?(ycHveOqd&w<l+0K8u7M4R*>SepWnr)Y^A9`j'
    'RAi7ggSjZDOolXTK~GpXjc0@vw<;`IUJg@Bb2Vzdfy<>}2o|D$=ksU%%HRaXe6pBSLdr1tF2OJYqcjum1xFYbA#WTQaZQFcFw#}<'
    'do=XPTrPeI1;{c^hiIQKItlY0oh&w&Pw7)zkP<mEWTa=iBhbTKGHBNs&9$Qkzo*iXP0txo5IN7yM(=wl%(f1iY)M8bpCxhVt_kvZ'
    'Xf{T1bc!f_4NPl_06~56tC2CT0dmyZmVJ%QcYLkA%G4OAOSfXqd{Q|-{l>zLv?g3;elNyp@~w-ZH@k#w*o1}@qk031i*VqYT!$>V'
    'F$UXI%@bpz^}W$#))YPRWv;a45*d0^Vic`}66lh>ClJi0NdJl&>*a4h0qbFU4R~TEx>P2JzNofuL<(Daz^W|poy2_XlwGIXWAlCW'
    'pt56SzEY+2oX>Qbt?x49Mg`HN%zzb)iO*Xy1kKu(-%NV}sf&BtNX)UA=-WO;^u)J`V-kcQR4j(~R&vK9ZnYv#8G8MJ88dsnHs|Oe'
    '%*^PWpz+5g$3OyPtNtVH#3r6STEZPnwwOoCtDvL7dtq}rqvS5blq^*8W)F8<tuxAwA#(o5jpu_6b7@c)_qU#HWF<3D=y?4Pfj1d6'
    'kJ+4JmW}QxUw9ERuDGJy!Aib$<4|4P)4SKNT)xc3AI`c=0Wo0AnVI|UDmYYh3uAVN{F=gb1z!TLhZbDD8c*k{E_=qg1S(B%_eG5j'
    'fo*mA?EHF!z$_UNM!`Oe=;(~Xb{ZFfK5?eRIkAj$u_X+lbHPw;z%|t>Ne3=N41T821$!BiR>j_fVYiA|AkUcFo4dC&-Z{IHp8IGf'
    'QCof3-F-|^R+`b*`=ao!sII~UYMd@T@}k=nzh^N8Jm{?0%S1t1vabaS&B6!2b`hFu^(w#rd(FatbzS76Qx|j<^~{Hqv1`6Qs<WCb'
    '1mm%uS(%|{;md3FEQ+5#$@4^glo@3hn(2-E68ro;#EP%ju|S_x=b~P}H3SmH^<tMNspu%_-zzr1gEUc-Y?TR8!mvYnO>Ixe7P(jR'
    '6v~JO3nf?S_ipPS7U~^2*Z!YvcKbCz90%FxNc!|*3C<sbk!Zx&XQMRO$Kg0u{*!Ix)Hx0zhU9A{72zg|oELwKNmP0(k)x5t-;82{'
    '+b%gD`;1v58bZ3{hSUyHtvGu-UId*MelbjRqaYQFbbK;fC5y9ZjYK%t3VHCXQzcjBYFh68@q?HKn@K2);R}{UCiaF*d-6YXGfv40'
    '{>33>JdCzZT<{n8lF1a)z7^hg(`YFRF>yEzDk<N^<bu8Af6Z26<N4<wvo-l|&Ioc#MS!H^>n`g3eJa8R<TBPtAw?B=of{VNHPu*~'
    'u+SL5r%sRkk7F}bS`lE0Qb@sxr5i-R93k1K^pilLHje~I6gYkf@P><>dH{1;7^o;aM+DT#;tmnvXpT9DeXo7wLs6#hSc~(Veck~E'
    ')(sTp`x`@egz4Xd94H3aT@13Z7-U7iGqLKd7n`a`kQ`M+2=Y0(Jw(V=J3=a>*GhUB`Q5t+a+DromdWEWWj#doT9N_eCO0F>AlJAJ'
    'QU<{w*%Sjvr16z)i+JiXJp?VTc`h<Y#Ww=>v_d97@5$9$RL&~oJdthN$-mu>&emi+UnfOKmzv@mTbLDle>WqUJ&-Sbb~c>9-p-gr'
    '8|4pHSKB5*ylF}8A|Z_qH+u#zLIn$DT{*LCZNZJaZ}h|dT9``07GxN6jccJmX{gfDhmn*)W7H+R@r5yI=UdrWx-?_Xfs<7t^5GR1'
    '%Fey<Azz(zXSO^6$ve4oKHF+<H-_-Y>wf^!zZj&q9#Ug#XqGzV=}igpBYmm5d#CTFi4ZqY{u8gPh!%w=5rXw4coGN^GEc%DB4n53'
    'LM=j$ifMc$2qv3{a&pKjA(^Hg(of12DnjhDg`5-mXJ0Ht@7k{wAxfqpjtMVduV)9-3Vw6)ohmQvmkN231-{Rj_p1Ep-?{nD?h+MW'
    'u2Ctgus`R!0A>)U9DvMHLIkf9H?U6N>B&+V`^K~j*99M-L)_mkL`IUH@Cu4K7x=b;^CeM+Vsf(n>k>m>gPJ<Sd@G33v}@~H+g0m@'
    'PAOK0q#JQwq3ym`S(>zm8^o~s{+AQgx#2jS%`r#h>r|%9z+v`PRKj+N9PSnHpr;TX-a)1oYATbg1mSyu)SmiOD+!$|y;$`AEibQz'
    'L_Qn-yV_>Wnd)p=2WMGA!(xiJdWMOI>YvcEiRLu(*2jXP<Yzava2*$Z=M*|IuHQoJmw~^il+7J0&^<$g^1=$CJc2Sq$Qg4%tQQd~'
    'B$)LQCJ3|j-z0njsVJ9co+$*9S1;t4^LsqNIJ*H9^AugVP7!IQAk=<YlpIHKi|>5F6QsmbFeoZxbq8QiSz~<%H=~7ZuOVtMrP%5A'
    '2AXrhN7w2C#A5JhNIGA^RbPOwP}$-nGrzsi`<u|t7Ajq2`H)W`QB=gxnZRVRDtqW-SD+n#PmxT-z5A$*xXzB)j`51j(d5MX|I%7!'
    '-;=T8%61Qp^F|lXB>m4qEQ}!<;xflSs~~*7xd_SIDxmv4(yu%{I<G`xr*)NInHj%&$RQ&|yedK5Ma$EFC&aAv0~WesPb#p44LfUz'
    '>t%wdex|h2+B4ptX?8HH4yzS%SFA;dJYF0^N*vD)Zt;iAsPvX)FZbZTyJ6XZ-D_C69tH_~D_>1GDVkL7=|epfY8iHZB&N+oMbiD;'
    't7ZQz*S$e1h(NJP_eD9fT)gl8hqoWdJWND!vXC1Bx`ZpaC)zit7j$DmvVKfQn1c$v=ePixzs%O8`A)Jjy{JvDY7@)xzYOFh)uxg_'
    'uB$*jvx!0us+p)6VEDuGZ*?OLujTww9}>ht_KzXO!2smwBP(LcK`hoz+guLP?P94Xl`>Ed?v^&q;Ev`v=-Cwv`qf=ZKC18iWx<O~'
    '(UPt7!6kVSDR}Q@?IbLTwS))`Kki(n&ZIJ2msh;O*_;1}hD}%Ov#MWdF$Lm2j?BVIsh{s><pohb$L4$QB=wuMbYRTd;CQIk<?>VK'
    'OiSU7bJFOY9M+W?ap3BhE;AY8uPq<gYoa^K8qtMOI<#06PkM{2nRJM~$=0IvYr=o_AwBh|af}(2E0Hp+^v9w4dNT4zj4l;II#T5?'
    'g;Q6fckzFWx)RcAUw9T38h;jaZ)V8mKR!np!1ymEso*TnB=8Z1gHri|sUuvlu8a}q;&H(>*;6cfwo%AJY*?D533m+Amu6`zxI#;3'
    'G!~pS@EV(hYkV)><%Gb`mK6IDAzFEs@}43ZiDw2DC3>d>oTewnN=`Y4qVoz9Z~kN_nT=q(`}ufvR>-d?4LW~^)1XlIJ{Yf_!Bhk2'
    'x*J@cVrN|79~}jV57&wd4xSQ(m0-IrhcI`9cms%!kPb!<xhf=M&_mD;mtk;Dn2=UWf>;&^Jii3#C3<a$kdk3yO%djR{NC>-veri|'
    'MM(6`52}LqCj?`3s#L{9+*0+$t7VW|#UMU^2r1=`qZ;|0-YUAqz{RfkR^LMi7_6}RajGWw{iCzbq+Cge4FkPy#7cpG|Bt=*0E=R2'
    '7KUqg$r42gV!(_F=A3g5sF?FHVh*SXDoaK|RI-8!0t$!;#e)h6f&waHzz8ae0W&HhDllJF&+M`oPI$lnyU+dabBATScVbU>b>*%a'
    'Tq&%{k|Pb#Jy|Q|yL!q`m+x9H_u7!}@{_yRR!2Yv)piBQl?U=&o8%5a@?8u#CRW>}`c_!WQ?-jJeMr|NUL@ZoW;5vNwf7$t7B}`k'
    'Sn%abu6viCSC6*-c~|$JclG_xc4_w5%8+W?pKRY8rzv2RLCB}<dHx>6ZPxNWE%U$d#F4oP%-k%Hb^hm7?rWmgbNSCV>k+A}mj7ff'
    'nws|2ehU7t|8IVZTeEO*e-1a5>8Lpw8^W`VbI-jiFL{_uu8Z1f+?NAe4}D?>efYH;H7^$PDr9Dzokc$o*zb`NL}#3!@#C&bTM5=Y'
    'fgX{sgp$m~rkHsVO}?bS1E5g8_8zb3dBgN6lD&vA#ZcxX8(tI?%8L35zAu|tLc~mOuT*5~kO3a!m;U10*TUly1?Ay3xpP{(a#@vG'
    'vZ>lJ?3vJz>6Wp~|NKmBY%gJ$&8tTI|3P(KRj5gZx{l~*x4@QNkUJiM`s(cWWqA<;rLwRDy0XC1y5lPNJ)&+`WlFVjnNLIPe~&%i'
    'Wxho6J%oPWYAEhu`q0zEhi-T#+tXiAZpAY)X-SOyz;mCz-t%oMOg&qLRrd^frG3~CE+Dr6t-+5tsUELOULn}uo+=AzS@_f)UVPX*'
    '7ny!j<6Q}pM{5(&yC<fl8G`ZHUx+PnvqHe#lp>P53jO&-(Q?<dVMnVXhB9<?vs@vf@u?pd+OQb;PZT{&G8Ciw0MEsIs^*9*x-E~1'
    'TvRPYh}=LI)q(Vz@5d@QSE%$z<^t>REE?|~a#S!&=9MD?SAQ=fkIgE$G~NWu;zg5+yjVl<Z|%wm0~5n6goRCpWjwE;^y;0eTwcE@'
    'IFeK}ff2H-u#7n}*L?S;n7K<Hl<BWn5_X@JoRo}Tr42vJv+|Mh`rYHw+QuaL-jsPj%hp~72o7rHRsL^R1V^?OmDMv!Es#NDoZP8O'
    '=H<tA5nKx2E6S$9vUDgHdB0AUlU(R%DX+xT8Bc;r#Y}zBUcr5vZvcWd1d*dou585yaeEa#mCndr6YEef-`}U;3d64sPF1PqYg;|W'
    'fGKG%auv=nW$r9h*{^kPSCV%7yNoa?Cv)qY5CG>W$z;_aK7E8>DBR4QLcvx{koFbPalKVs=^&gA#`esKqnB!dz}ctE0vg3u<s@VK'
    '%uN|1yQc$U)p`r@Y6&0Skay8p$lK)TMR*_PEPkvRVk5|HCFFDv(ORyL+Qixl3D{Tgb5;3Ov9Ojyn+SiNcwCjl&RlOt##d#qX-dPL'
    'U7qrT)0^T*Gl~4ALKlke{OAz17>BA_jLsVGf6UPx%Z;e+xB6KgwyZ{T-upoA@zV7J&W5@rueGW?8YV%lEQJVYUAgkRpB1f_&98m<'
    'dV8s;+5@XLJ^FdcZ<7tv`4Mj#`-B(-veuPTdXQMcLymI6Z6b2AhQw@sHddTaRbbPMQ1VN8`wq*NU{<*==gD=k=Vcb1?qMLTTx9Ah'
    'k6fftx8$TNBZaL+7g%TgZ?T}ku<>r2b=!}B<aY5nBW0Vc`v=Fru8`$irX`h^ZFo()eyKvZi%E*?_Zmezg6)6s!%op1&4*7v!#gcL'
    '7OV*<FbqaEq*CzIB%GBiQ@AgUz^;2F*Rpma<3Mf2eq3MWj-p_n{!bceqxfT*B3d)}!UASMRljAfk-6OsI4Sg~3qMT%bBdE(#p`&P'
    '!|*U0N`WJ1(Y26}eAZV)qq5{lEU?CE#UHl+@<#-3bgy!;mM0}>T~X!Df{=;0D08q(rQIdBihb_%2r+a7@BUvK!Ku8P!g$NQPxmRn'
    ';(ydo`e9S$8&}0^Xdu&5%0ua}HCa{tMm>5$zHo4O`iFNh9b~iYAxvNlSmkzAp1(P!R>a+zw+vt95;9mi#oVgVTshWiV7rSq&&cFT'
    'jopOhwKMq?tg8@f3EYW^|FhC-v;KQ|<}}!t`1JGlclVEN<k^Vz$jww_9LkXeY9xA8No<mN9^0Y%K|Tk4*^XXSi?gS)9pkIS#yUY{'
    'haFsfDVLDqcavf(ZYeCSm%~KzuLyz6V`52YD2_~IXy}%zlTP#Lc&oPA0((>C)U4=JA;`GZ<5F+0ib2mWGx$>7iJ|@@uGG)Z&)+{F'
    'ARurE(yYgd7~NK&F^W5ae%yi3;&AuNqwTyM$KW>iJ->{5-je5z59@*2PVSb3(xyFB<6UA#k&!n@@Dg<*{TJ_vyo_jBTkgIJuX`TD'
    '>|y&gK;p#RBgV%hpZj#>E%%alEYS0O^!2e{9r$m*waX|;=bNld#PcyTK{T$4Dyl?&^@96gyUfoQ+x*uxjWlr|6%$2i?ET5Fdq&BR'
    'Ssz;5<gQisQdi%r$ejJJH{HMRrjzln#D*8wR`h8_#;Gc_80g@`cPcJ|^5Nc9TOepyp4s4kof`jdhT(sr+Z?j8if(fr)t#`jx%bfu'
    '3&m<KtK^<&RQIrxE&VgCr_$|fl}ie*t&u078gk|1$7`z;MQ$Zxm0qbTzDSB3(-?o`Dx4$=p5R3Ts;)HS5)J=D5dI(Uc{WzI<WC)k'
    'rfjjmyxwP%u}K+sfS3M4OXvTC&Z=@GQ1l-N{V%M^ok*a%7YU5NS9X<<+Y4FF<PHp9gzK5gIqMMa0SUt&U&*uJ+<T*J#G>=a(5UF^'
    'S^S!p`}Jz~{~Rm+uT}L&tE$B3CUSivvQNoZYLNl6vr35q=RnqgKI-2%?vUI```9P!sd;a2wfxV=;(s;eikkASKd#eA_<4`+$RD=O'
    '|CO9?SMKk&uK(bapWfl8O&9)$Zd%JTh3PW)EthN{P>eT&<daO$oT$9wK8dRA58gH8EF^ckhFnw2ugK?@net&_nkRgGy7s@%>yEhn'
    '`7*!EosbDv#@?N!f)*6+k@Cn4h}XYWX-N|0M!>qCWk{&yZ7!X6{5bIao2S5<<ha%Q?>WTc@h9df4s?%O+?}5MaKEMDp8Bnl5AA5p'
    '6O%Syg;kq4^ra%+Il8MH0Cv^@Rb&N|8YqB41Gc)hO%*U`RmvhM%0S|<T%s2MLudEP_hIV)(`Hq>jL)~HBDZ_^L!m3vh~MCsIQz&W'
    '9lqin{$e=6zlHaKPlLW+gwTNigI=<*G)=SQ%%2yppByR6Q>UKC$0>;5-ZOVXqeLzbp-<I|D`C@i^CvD68N<<q+$BDKZ)^}NHyj=&'
    '`k#o*rd%m|9ac}SMn~b2oC7)wX#PCN<7YDu=oneObCpXC?e8K~nMu=~k5Iv{s-K=+_9nc+|F>=Kd9_5yXAZ5-mt+Xp*z5oK=>{*b'
    '=nyIA7qOCmKKD#TZeA&2%XGR_WvMab<Ova&KQtddg5817M$VQ5J?HO`D!&8t$|*?};_SCd`+TXRtPLf(RYt`|TQ0pR|Mup_AwE8m'
    '$N|}qkMZ%ZWZ8GgT`ffqKzRvwRc2KF$g|1MZ}5gu!CDM(>K3q7-SW)n`gH`GE2pR`BKvunsG1-nY*KzWLg~#uh2kdDQ`}*kw8EAv'
    'xI+B?9@MGd6z@TxQ>hr^V9by4i8MY}B^~S>LQA7|$(A;eGZW3lx*zc-odx|m>t#!1w+hI0W%6esBIxip_~gXnkAx(SgsN93zx-DG'
    'AkAy6<fmn`wcuB~YW={dDF6R>`l{Id%?V4t{q^Kid-hY7*y`I#l-C>m#c_?IA6JL|urU{{@+QAMuK9}lMc^8R%}xju-26Akwcm2T'
    '367#D?K4M-7QZ~MTPz2U=wF`TtPl{?{1?Y-epG<4Uxo0hw(_X*XI*mbl4?MD?57jFegNb4KO8qI{o#ZkBfsqYiG{Dee#PX=PbbKY'
    'pwb+G70Jl697e*p2XUVlfVo13-+9Nu^t<HPa>-rr9tFE#nfc#=ZG@5rL0vSoM}9_f5T=a;>DjAM4-T8dqW*wAxTzo_=3YcAhyn}J'
    'SVqD4i2%kvuz`PZ#%0aflNB`|%x;2*l06K2tV%nzpJhiAYh>(Q{(>>&JGQe()gEe`<_cr*FwcR}XLe>qG?(2)>!3@F7Lt_p0E^wg'
    'Z7FCRkl>M(u*?g#kY3H2_V!|KG1^fsF-8ZPMQ`DkK5uQgYbu-~ez5miNEirvrsHgglt2)_cPj#0<3n_=(%v1r{TWgokqz*Sp}0P8'
    'RJ4ov%qJI5MDix(IY;gtR%w=++P?cs4TGFBHO_Q{HR%YR>DP_`40(qLugRy&IsmH^cY19xNx3v_-kJWp8ruF~YjXtCgc|VY6sY?}'
    '1uT&bnvcUbAIagE2RO`Si0$Hs;b{rT<uve^K-9!z1~&YuA;96)09y_MY)r%vNaX9dPrcBP&SB?D%#VW@%&+v^X^+#b=aqM!8u+Wb'
    '&*lTNV}G*=4n|Q`MfZq^f{2JU)prt^uezwwyS_>XNA+ARawsdiRSkXJL(1D`6@XKHfKUJn8vsXB0K_Kd_#{WfTuky95aYjB8EO>h'
    'g6}#QiJdz9GOWQ~ZTkT>MN^z6SdG8heSi@ckXgJ88jp1$0DE>|jL$xz{rwn0TpGj&v#$G33oG}^b%UTz()N&GRcJB?AZZmlx|bK1'
    'QrT*8(>tVfP(Mb<sYWP~JDojj)%cQ%^78U@FihSNcu)&Wk$N8I(fuyc{HwIRNt~%|L;%l`%wx<KbS#1C2)7H8q0dRL9S7Nsv<evd'
    '_4r1`&?zNY==uQ_JB+9pJq@TxDk>_fe9hS45*}YuQCwD5HU-b*J6tIIoP3U&@&txQ6CFPAn$aTYiC|*C7n&t{`|L%K)!XfTU<2|m'
    'y#QRG=_B67B5zYrMn7154#(jUOwOi+_PQP3i=YlN5jXq75F7;aW6sgdp~-iA`uAE*=3<NafZTRW@vh3d11@B~2jVkKYi-5%?OCR7'
    '?Z+EO=7(=NY6NvYYk+GYbb5`=jR)oIzB&nrPHd9)T&M>Fk@cE*9@fVoBUcKRmvEk31(Bz}^D#s<%ftM_RH4TM3B+swhe+(?EO0|G'
    '8~6rB-4a9B5@h1eZ1aD{ztu_T+YiKNheNx=TMiPhllY5R--*+HxnKNv5zae1Fk36Ei<m&nR?kC!NT6BBS`?I9=kfjBY>y2uHupR<'
    'ho5W{rNTXMB1P~MNn!itPMKlajbF6Y{=ib62^w&Kj}Iu0+Qfd1$2k$X43G77SM-hSeQay=O0a4Rnk*NMh;#xqZIThirL&X<{y)+9'
    'e4geRZ}xC@4Vp~2a9{+1t!R}mzS1ed>X2Lqj<o`9$9-?>f>+;~mqD~oOBvbl-Oaj1z=)O5YY(Wz!jM4NG*e@rwUT3VXm%FHz6uP;'
    'aw1fkp}=IcKF|0b-btikfd5v{jRMVVB@gr_^_MLy@H73+bI~1UKq?PLQcal4qCkpH`1$#LrD@rn*1;u`<H&Y$`CR>gQg`B{uIIzK'
    'oAf;Q&~JA-5i1WQ-*qZ`^A*vTQLLi5mb?!=9{PnO1{m{)z&lf@jQ=X)D?X{vJN5DIfan;Ux8hZ?JH4WV0fLSYYwZY)WU)%;yptJl'
    '3WUnsQlZkg(n4m6jHj!du?b6~x48$$0<|#a;yzRUp{o9`>+%m(zPp{TK;UJevLR2XxMvELbDn%<(yKZ>&*u9F#vW+QZs@-!UU&&d'
    ';f0m?lDY|B*Uw+*k)c8f>NWXtWWV02cswY(gX})SZG^i}v5~*WQU21w!X0Eq=af5(iP%eQ4)63jjI(p^QB{VbnsQ7uGx%LcY1?tm'
    'O)81H>vCog5U0vlM9ZSR9D@V(dY-#I8XAXuwiX)t27Xn+cKMzB^&z3sJN1qwG~HXer2X;2DX<bp`#1j`PZUlEi<p-vPR*lr>A(ES'
    '#I9Mf4Z;FL^nkTc<?x|y{KI+#iTO_HxL3k=kHvLfV)e+0`Yc3P&5+Dv5#ZSsQMWXNn$AOnFl;Hpc9(CShIr@s3SIm!%Y~-BQ}evM'
    'eDBxnd5#kzmfP!q$1RFXrJPDqoyV%z*t99jS-ttQNdS?JSiOl$B6MD1%GVo~HxASi>Tot}3&`q|DjKnR?^L%sD#1|4h1;yt^IQdj'
    '#@O7YYTyz02*rA0!9AK^-Y(Rdv@Yu+)WG$ovQSgKyGf`)uP--*8U%8{?u|h5lz`RafLGuFocwV<h_t%Ctk;@fnsaj7{Fm&t-7;->'
    'GqU}ixx9hV<AND4lAqcNQN;H3C^7*R$8Zn-$mTR<g5m<ySZ`g}%nJX5REV#vMvw~n(@Uv3j8}oWH5sqfJPz{hfnx!5>zDPwf|r#~'
    'dBJ?X0qz+fYtwCzH7X6v`19i30S=P4eb;A*GgX}Sdqm!rB@CQVK2~lkdJ(Ko^Kws`mC%U6-!%D36N;XT6@A}0evaoKQRdGX_R&x{'
    'IXPIUbS!T}jbDJw{*?jHH{2umB1m5A5%aA_&c*mrN$*+DYdAcqWJFs$>sv1^5;@PzGIhW+Znvy?YQKB<bT|>@efyeU$RWfE5q<z<'
    'u#FJHCH}*5(e+G(^PxEx`vHu~S*0%Qk5GfZsfF`3L=@YYh)B6o`h3J@_hA9Fre&Tv8Hf~e%CqFINKQ}hFn~=gdRZLKN8|4}P1`eF'
    '`C;T?{Ft_FP>Hq%uM-#LEu1aHrCfU@N}z<b%H)BgLrr)Q)SkD$cMd&bATFX<HN+-wLs2U*l3dKNLc`I&SOs>U^MYoy-bnIlsLt-O'
    'MM`U!DSFo~>we0wNAgJ-1{TGLU}qw~DoOI%o_xFni7=3&Rxsb<x;r>OJ>6Yr$WnXy9H^Y&sp;oATZFi`Yd^@s0vddmnHj?-f9E50'
    '%vk`Q1*Bwa96^y_y;1zR>Y@ydj+SrKp7QVk3L%5;tx|>&6-b!dviqDs#ypzYjT(KKIzn)hc6@qRaIjbZC|igQMV3F-3|E%yXRXQ$'
    '@b-Fgj#0k$<tRglK$I2AbBpizFz9c2$H6_98UNI+97PDj+L9bvL1Eo$JQw8Qz2~8^TE!7NwKAM>fA?Q;*pAd6Qsg(xiOr%Pj!3>O'
    'RtrCzaKKxy8XEo_<->@-{U5rY&Ku4g4V*|qHCQzh`TW&&HQfMk-tJKCF$;Tck{`0U;=RA(>hu`L7cti$8-;5%|5kq~j)l6$%>yuk'
    'Zr7mp;cdI`!ipg1co#MY(s%RxgAT8IY<$D}ng|7tP)v)r98Wi6J69#MqV*?Mw135l<p)7O!F@+G;+$ELF2^id7pg#~w#ymYzMLs1'
    '+P-C&bY9k>AhNZzJi+UsZ1`do7Ap@r{TTvX3Y2K)+9-C+?jS3MJXT|8dS~s8$})wG-T}VQ1qc0pr)9TYTwGc#V^T@i4{Yvix)ioa'
    '6*PnPjzDQ%r7>(r1k(M|c@H)4BP~YtuV(29ycSsnnct1UTc3}EChx@%xe6K-iy;bu(*J-*bPdo>VLmxEu5n!1VI`w5?Dq#9XCl|5'
    '@u0R|n7c>#Aedgs+d#{Of@h)2Z4W=`!gjj(u!7#BS~03(LG9yN^`Sc=+)I38y4;@(kWl@9*!}&;%XJ_(mUvkl?e<s5@gnrMUyH#M'
    'jt_xJei0HF^`2kKQt)Gu=&X*#7z*fKU~`wGje^a`wy<M$-gJgO?^i?I-S)%oBN9sZ{r|B0p{Aq0Z-_5g;g^fpq^uTr?gZ5m6ROd>'
    '7B%@*ZPa(0`f-=qj{CHBc;)INPdc(b+2+X#TfZNQ;S~#vPNti{(h!d$rqJOY%6lha#bJOp?_mW=_wS&69)cJm#$~}Su?@ho-1GRw'
    '=AgzYf$bSqpxjDDr?;$Fb{LC|Zb#~Z8lS3OjZgJ8g<C3jj6xi^>Y!6x2y}fUp+>Lc0doTnn1c(|dBD6Bbf^lF<#26uJkw}Y<-(jU'
    'P~N0bBOWs3U!y8ev@?kHJYl-n2kO^q{eFKR0DbGCX`_{3-IhrQ9Ag^;P8AW#%ZtiA%#9HH$o>t!D}yNG)POnV&^*}%bjy*z{#dA0'
    'YEuEBH~f#EH4Z2p4MT3WReRYJTA+L`jRaSOB!l9*Ot%)2!K_{_Dbl`M8I!WD&)1VY>kOOLz$heFTXslN?u)iz@0h(9J1B1$Tkw*V'
    'Dq2&>)LV;epe9*h20o3@I_fBaK@Zz7&qKdEtUuizkS=L%_a0C6VQE^OCijvWui&g<bWSU{IT707BwKtO9I#8Y-s&^L85G8}L2Y<L'
    'MST*{nt=<M5kevu&$2Ys<-#rK0{X9LjZ7H%|MY*M3rcGDCxZ6m&F@{@6OrK5$=HhEY|V7dHq6<1Jz;&lbL9AAf0-d9Z<ng0{P#ST'
    'CPP2XQ%xxp{`Lb)Ggw@)h3u;7jD4HRFkaJ##OEl*#$X$UU#dFFe=jClvGgKBeAD>21)|2DTkDJF9Xn$BYrJiCYFj8aG~SjGx@<l}'
    'XaG|W)%VS1*@8rTb`LdP6XMEv|F)IoxEYE(qxRM4V-4Nb4aTqaBERsxe-R3G-Y>$4ufE4F807MAC<!vv`4qjtz5l<u>Td`L_mv1p'
    '&znreu!Ydv+IXh+IvkAze)1~$v;GN{==r>}dZfu;<J<|i=jo%sF<Iwyirg>rUtlY(dSX)bP1|iMUxW$&eBSEt)P2tH21__DY&!qW'
    'oMgP-5cW;M`FZ~L=d8G+3=M9GVPT)&pEG}efvriOIMu-U(BY-|=Bxkc;kAp#%zmOS-ZRDcdW|m2#WRQfqpMWU6we@oZU(5H{qR$|'
    '1XzUBpzZ_YXb&UPr@1S{E6EswaFR}Lq4a@8%H6<)xOAgT*L<KqE}VWr{vSN<P7*<vVIXnd=N51ASDLhHo1#X3XoZ5=>b!!XtOv(^'
    'lg9=<r4THMg`E=C5D5l%ehpt!-ubMU>Fn~675->}9H<i1zYNd`5#9(C^yl#ICgK}7+ov5dd4t0=zd7Q8)%Ds>|A#QpVm0i>dE>3u'
    'VigPszaDZoq!tXA0z|&tYt=)s#O-d#wTR`=&>l$kS<qFPP-w8Ex4@itN7<@gL_)xBI55c`HbTZ&!b)piFhOZC7m4?7vFI*Nr?D-3'
    ')^3EgYL_}~-*+yUlyc0bG{Nr}B8tu{K|M!2#vf|!6hW^Tn72jjk1swr820wJCziIxad(f=liZ!-Ny2C%9TWh;gOK_1SN5C<bc3zN'
    '5HLn5R}JPMLFf@1Op49MQPOCBZA!#cu;X3f<CnuBUi_L>7&wvlc#6GnTx6CPXlP!jW%R<<=!yiEpF~lwEUg{D=zC&NPJcn9$K!y#'
    '-=Op)q)cl9z+n_P*Z5_JjzmCSxD<&OX&aO9hY>|Xv?Ar=Mv8a7orc$$6s}{)u%vvNFl&9bmT3uj@~bBh3$~MV#%l?eZzAHhn_Obj'
    'W>8j46g>LVYOp`C<7Xnv-;WVQF=XNY{uSO<NuU}0I?f38FW)vP3HN1+{>n&GOK{6Ivr#PP1Vv>8?f7{=%8rBro4hd*#Wor-8#X?D'
    'DwX?v^JK%9ghms_RWLs<9VSYzCvv39c%u1)NW_dLkL5ECi5wk|wT7k3VfZ1@J#A=v%>qHZch+p|ty!`5UMTk3Ns(u{Vm{3W+MNcq'
    'XxCuUxM&Apf3$QgU~bvPg!+tMFk8Sm#=kI|%TCs>r-uNvTmE`WUx0BT&PUC_Rt!@axtz#+V|S9<SKTyaY;6=yQj^_y`*vQWYkXc*'
    'R7B`(MWFk!S^x;zzP#hOFLMCzdmd?$$SajsqieqADaoxi1loqTRUqEmA%Gd7l`oToXMY9XeaM6dhG6Ka_69_|v@J4VO;51e2XX1?'
    'PxFbZieLh67LvGCPoF+@fUQ*)P}sgXn!S(8OJ<_K%zRHCwnE5me^nIhBi&2f!&o1$7#MO=1e--SX>eOJ&DFe{YkiXH*yG&Y<zRzg'
    '6}YK;JV<W00~fFT^O26?vr7BZ`|0pu0X-RcZN`Tgh+?XwA#4UIoo2phD;R#!Kg~Oz)CzY#IuZPqL6@tL-UkMxz)l;z6Jx;kP;jd1'
    'LIm?;Q;s7Fh?yBR2bA)fSj0PpB7Ap0<QlH0`l10?yLWv=<7WO+0>duCj$<3c7?0#ns6?FCbSNV5K(O(5_E13yDEnuF{C&iqweQ#b'
    'alcX#PFB}p&_#~LdF<S7Cn-rgde0-R>C6+tJZ@yWUf{ko{!myqGbaeQ9l!rA+nNb}IK2WV2(`XDCks<=9r-F~&X@KjyVbh7)vhy$'
    'c0D!)di8|%Y?WY-ObQx9HrpBAG=G*eBY=IC*Gla?p31l0;^64+LiHK0^d7BKm7%>5-+iMcoG^g)+s}Byh_(6&V6qw3TfxK`U3@{>'
    '0^;hzPQ8KdaKxbDJ?J(WnjQqlOEX`)k|{8)DyemkLp0Z0F}r%Z-5#6P%kqO+lnYB+J&y3%M;lt(^D8YktB+w(77dm`BW597>*3*1'
    'iWp0qX3Z^>0@jl<Gk!hvz1aZ?Lsn)(uzVM}Efr_7xU4bsE0sW_uM+59B7$LepblB6SKjo9OhytAh{E>by8y|^y!ZbM@C;FkeFDtj'
    'u6b+=BQ&q;;o}^XrUA8XlC*(C9wsD6&@K~*a?kfNCs)~8pq4V1T{urN!2p~v275f6c980iTDBu1nDlVsGMsSht|<d+9Z22|2N=dI'
    ')0dFnT*<i9D>%agX`YIU@h-{4Q4GD0cYlV|$@p4NP+!gkIc?j^2k}*wts=u`cx=0dq)t+X$e#ikG%gc>X2eZUX0BwbZ+PryOZ#@a'
    'fH5OzskGvkn)niLuCpA}S8{<KTgm8(H;nM`jGIa~L{v5iAJ_P!@Qx$0ki@VXW_x%rz2<J5V9ZXID$^*u<UO*)%Q*+ZOSk40f9JsS'
    '`e1OIFq5qa4hr2`^P7-@tFNqEEvZ{OWF<Fg%ewXSA`oTbJQqDixHsPK=@R8iv~Fy%Uqj@)Y!P&ozTu2(#iDdI{erJOj<Jp-X=&Dm'
    'DB;yTJnk`>a2H|6ES7fe9Pu9SnG@b~<bVt~>_4^ToW0oCtBk$K(8B$Mc3%*Cq|IE%Ix#)gbY?VnW^^cqIbB~LjqS7k;z6Kp82Xe}'
    'CEGBX5W+;<boRVA9heU^HNFRmr0Zb`((sTiyS4cd3^0ZGeXXg-o4^bvlQsS-S+rbmr(P$>OshX#7NU{v-fmdJt1(mOg3~QF+&GZh'
    'uaPOjk=&#SE1wKxcMf9jNcR=)D%?}JqYxx#w~#v~Rge;1BK+AY<DI-6JrA+_(87A7FSO=Pa)%<PZGK5SP~&Y#FKgL<BYVJzF|TTZ'
    'ZRc+!udi-#u2)T)5lr|FQ1M-~T6Yyg$9rL6_;LtjtE2ZpkGDDu%GFn9cGj_n1#kRGu`%M=8PIe;PEMK;Z}nj~y{Cce{&}#12Bg=_'
    ';b&k6!T!81N=5q2aO|lIyXG+_0f(hu>Q<p9evXqtdGRF#@EuI_Fb#3{4o5=N@F8}JRgM@=u#PS2Wmv(`cFv3uPuc4~9X^ABQN!}u'
    'eVD1<<0wdOAPwpK2&Y(`2(PXC8u0@c;hi*!^{){OcuO5pgyJFTJx3&nn<kR$%Ib8tRcyxYmPPSMm8Bhd*;Y1FHVZSwWY-q216Z$<'
    'j}vhy%1s9unRqZv=PT37rdjvlXUg3vV_7~x!^(yoifN{7OhM4LLLB}aPc#VM9(<Tzav;u@#q((SV2_E==ENbu&+egxz|Zc1&)Do1'
    'x45`~&2Hby*23)0A0^E0t^0)8-Sw>!wRxkOsBnuK7>7Cf?1Jzq#EfULbDdrjXo#g{`v@*uzF=9ScCIB}J*CU`eNI8ML7e7(_O?g-'
    '=*FYLcN>f&;5;MbbD^0|j8P@ecenY-@17_mSlq<>>`lLv!c+p&zPTGg<D*{2IJwA;!xLGo9?yAD1DMPBII>@OGDevgx;WCZHz#tQ'
    'Ne!D%6EkExcKtr;MuQ`95x!)rZ+PJX9$BB#3YL-2sWbLwH)Mmf=@#nWjbR<@-s{8FcrWq2_SSrVFFq!u(dqnMSo5LEM^Dy0bEOmL'
    '=|hXO1+e%u-g*>>k>m}{1M$PvFcewvrr*TFGlIYeCy;VQ1J60hh71!tp1q_;p$+2;lW*%7RPqlD!E1~8bt4-Pj1KS!deGw-{ppuz'
    '_m=(O!&dcne>H?(k{~XUg=@|dB**zu-pJj^L+L{s#!_p-Arvbbg~aGKJa)e?)QNd99j0Cx0&U9FVJ?EC=;a`F7GmRo#~OxF=G@`A'
    '_ZAgA>oh<hi;H<DpYi9inD_CD-7eBMVSqzCzL>^U=Q$hgUFWIUy-JC=s@`E7lhY02Q(AsOBGRYtpZQW(-zzxTBX>>1?`-Bf@|vz`'
    'z`V7GFbuzv@zc8)eLK&X&LUzk^;uJT7A!;}ri}cmA9FMD5yQF$Fn$2ET>x5$hk_8qR+JK6)_P3mcVf|OX0VrZV`iTt40qfyVB8=R'
    'WLP8(OT;kxvrjUiW-ueNPSh0*77j$f+@vkq0_0z4V=@zk3!_cH7oW6)*rpBo_whpGpuZHg>jz0suT;NU7h*@u!ROyI4O{{0A4EPL'
    'F!K^vJc!zH%?P}hkIGzz54W+vCJCEj^IAaRAn@FwjYMo^Kv$d>p|k(+0n=;hV~#oo*QfA^&ZkYZa!p`~>O#f>1~56nm0=H)^TBq!'
    '$#)^|wPnH6q47Ai8trzxvIaD6)`!?(Fb{FWz4{P@twOA{!vkhrLfFV>?SjVJed3@-s&1=7@%$_|ulf+cTIYs+tqpZE_Sg|KFn6mj'
    ')V>UJVKTPDES-4%lLXIs$nvTXrfW&e`#8b^8_41rM#G-TM%^$-delz&Qghg{b^-!M{76rPsDj3>e$c&C-1uJXYUZCmIUJU<%Z~W&'
    '-iG(vz}U@+%*ZKaqZzYd_k&iDy9xGARVo%ka%Zy~WCXOwMS|W_u-^zh3fh4AWsuMW&^hS_yJtXJM|fSs;4$=hM2pVr=MjjCs`NOT'
    'QLIZ{S*)AG%y;t^O-@NMVaTQomPbb*fokW31iW1Y^C0v;#RPh0=k#ZE`CMn?D{bMWE=tAvh5L}4^e&u)*IN5Pc3<#a0DoMp4Wqs)'
    'K_lcVM<Ur?hg?r6_Rl5cbKk2%eUuJ{-0u#icdSEibd1CyyuA*dEQJy!rD9c;_sX>&LyN0maS8e+0KV+xFj(wO@9S&}zOgk-@2&{O'
    'Zn?7-yG0oXBDr&`Z0eQ?5!5XXe7AIta1PfpdSCz>*V`hJSr{CGGh?UihD}iWp|Q>Z=SZ9khPNDJ@{yF^u!1c+K=NLK00~VIz3-a?'
    'qxV6bYZ_pC*)b63dKmBJdYN_P;1b>~rJ;}Xh?{!00oXcEM;sVFWgGTtP8+vvpi!dM?EZ02Mi<92cEgt8;yni>CRdk5heF04r6uqV'
    '=eh~ypBO~ih84t$h(osRZ{Ow;)Ya3xzfT{9x9z!r6773sf3HANk1T|y1px!#l{VBuGT9sF*IblpyXUTfCXYMAW;=MU4N+tDp5Qx~'
    '^*jwqpOj|p0q0xL=Fy%NcTBC3mAKGf@=gh2YQTk7oe}fxoEjh@S1{tXTM|~DfJ4(3+T4Rz>P9c1<u*9i-u8OKt;Vo()#`vn$ff*I'
    's5k#9qM#02pd&T85ptauaY{@%Jc2+&<tbY}Jv@VS3WHWOeIy3WLM2GW_aBQ*&Opraq$Wfog*@K78EG4(OSX~BIy#jFKC73<j4b`h'
    'Y-6d+2+Rc^o+W8^)}?ej4ANgr&{*dg`N$n11^MX9l0io5g)tr}bj{g`0QZsJ>3l%Q@0E@dIu_a9b;$(Y7l@O%i}Xv07$jpF9?1n#'
    'ORY5f`;TfM3)4&Uq!umE>U*4F9~>mp^Eg#bklN%8{;Ewp*DxeH^O8^+(RAEqsX4J;ua32+c`y3iDy+pJ&c~p~Wf54z2FCubCIV!z'
    'Cs~TrqZ#W@OOkAAvx5n5i;9X&!76k=GMiw!9@$s?nz?UJ&EI3|ONz^MN9QqtZS3rSgUhi;uak<}v-Q8Z>Yw294uLc_>K8j9<#j&A'
    '2OQA8MvdDd52X8#5cY}`UFf=5Fm~#lCY-#V;OMeBqQLj~&V+Ut-XSh9O>+pC)m?H)aIO4DNCosj2L~~+#ep7*z57q*UJahO{-kCV'
    '_S3fF_v1Hn6f`(2f;umn{r;Rkkz@>a0TZeA@6VYrs)>sdG>C>coCS4WG!Aq7S2mVEZ7lDK=qc){B6`q*0srD+rPHtbw&1uBDyy03'
    '5O>Z-&U88{G5Z{JJuw<Ap45gGqu~H+-7s#qv^BX|*XNyyq*8>Dro3@m=}CJ~#eVB`+%2Zt@6}m~+n9Fpswk&wwaPe-lN}IUs|xKs'
    'zG}sah~-L;V|6Pbr86_L*M^1#qyWUT*CUxk4ClmawQA5>>CJ1GyMaeL+X3JpvRC_yhAn8(YA$(zx@ZoJI<`G)5-e@faXRf-RUaJE'
    'y|TSb$MiNvInGPGlwUzeG`xFQ!jaB!wa&_sjp6o4qD#Yy_Y==KBc9%E1=963u%ga&@DDg0N>i6f@-CidG(pQlWEKSx9YpThU}X;%'
    'Yb-ZInwGF*&TwIwUbAIG{7&>lcGOLDS;<NYA~!9~3~(3^OOW4)-LgwUY}a<)t-nAIcz!!~z!b)@YDAWef`E%{^e<XO925C<hgE@~'
    'p5upOyaYL-ZWMJ+{eX|udnqXj0%k&JU2yriPqd_lpnepoOE5|$MwGmDIuR)cdZ<6?jqHeOm@;u<ATx!mBk@FsEzXOh0c8e~OcbCb'
    'A5o<5Ox)t0F(~XH>FUM2MGf`CR5ZcW?PypxaB-n;e$Vf>#=QR0wpLYP?RDPYt7Fy9xm6JaI_8U&62%io!lvBZuCkreSw>G)Qa&vt'
    'WeauLG{j3H;*~8)CMIR|02W!TrjJX62qMfOrk6n$3c?d7pzv^XkORWnU1RUrV2}%Im%{4BV0gr3E27f6mJeudG-E2gQEW+<4b%Sw'
    'Gx7I41M?Re*s^scON{}R?(hr|15%j;MkFo}dtINLCzL};*|`nbpJr}^mY>|p%_TX+$(yN7@QT;^yb>27!EoQ7OmiW2;RDXKO9Mda'
    'Jl!2h;}*xQOwZo?HJK*7ktnNrjzBTk$#BgwnA-*R_Ji<~CqJDcMl_%IOd?8?o10r3c;z(%GPUi}<II(!E7N?LWzho`xWS%nPCM{*'
    '#11ae!@+qhn2oB*gn|i4YxYZF<0=q;&~V17@mYP+Ht3Q9N+Irt@Fn-<=H5F6h&*g*Uesrbz}@shgNU{$#}Xk~PYBM0U*Fd^(ka;l'
    't~Y|P36S2WVMcAq&VV!4ux1_9cn*K|0F_s8WB~MtgU&}C_v5RKi}0}n{Q?!pYDnxr<nZ3epu`RkAM{!LfH;~OmjEGV(^#<g^dcE_'
    '?5^sIp~%akeL{8Hz)NgjgfaA$2T5d<yr)Mi>|7U`wzfjb+Aa=Lc_?kRS-xb?+6%Xizy76oJLK_%)MYv=*YhzV>ZBrWFj=<>AOFWf'
    '#ehz2!(315z$_hFIR-qRtTr+cA00S_RJzitGdrB(W&inZ4$h<xPzt8mpc|(H8~N}PLl>)@L=^6RA53<1bA*}g)Z(D2gVjRV4_%yL'
    'e%rxoApsmGYp(>YlaT2ja%dW&gSAZFWv!hP;IwXyVAyx&wTgOMO4-U@hbDK4mCy-=W29}}*cUudn9)p;N@K8t*CX@W={fYc){G+0'
    'jEA}3rQXR6pv6sqW6NP&xWwXG6WAE<nuxM<<VcV_7ywrhev)R1ij_e9c}r{VwDSStjk<-pY)Kdf!!98wX4YR^$oFpd2Yj2R3ejnY'
    'rwZN<lyXgkTz$ubE^hnD?{t2-)aw}8N-dDV)VPh~Ie{dDwTRv}lkhbMh2?{!i{BiMf(EfM7py?^8J{-otVnIcH&-WLCwgCzMBp?R'
    'e3v@;AzNU9xS%G^?uiGWBaNOkNy;K^MOy(Q#Ww`?-xoxC^TcZQWm2j8e*St#T1aO>KIS-sCWZnK=Oay!`jVv<=UYQE0NrRIT+gPt'
    '*zSup@Airv;*l^0J46q$=16g2r|KO-L2NdE7{WTFPbTO-!D%rch0o5>F53>0E5rQni@@UQAsiPA!U&fMF-}1FSeeWLu=#{ky1Rs4'
    '_24L^>&%pvgEL_jx$}xX<BR%kL~z{j#S#YG3@638Rk;mCv1W?PeoWe4%%p8!ranK*2*}eWwCtpkxns1>i6Z0dMW*0;PgNs!ZGU#{'
    'k{}|dyO5gfaofRqd|{<E49u~_<~~IBn3#Zx@#Z@j2ujo5@_LJCfBzU(xzWA$hpw#G^uYcCHq^ds8mK=d6uz)>IS~*Go}^CXqoPT9'
    'Q$;lI-f^QF-{ZQVzCg|XtJLXmFN&*8R@CIHI14OpuR)Y`!-*}j!eMhcNr2^Go(+S0<kN6(gBOxbs^4hDydiCMTXPx}u^0G<fz?TB'
    '%?Z=F&05D@ARE`zZ!4kCh4IK9?8>6k5r_v~Z>&lL+otY1d-IuW=}Ntu<7t3V+D<u0^uiYh5V>KcHHl3@mqp4R6Ydg;JkHcKHIQWW'
    'Q+-XSX?^ezMyXarE@rlhV8_|SeAReqZukVzjW6D%XO!#Sb=1KN%cX&#ID!^;aJ2A!CSp&XK!H!XS#8X9d}MT_-DG01ZnUX_XM)Ev'
    '0UifMIEO6(7<ok#M2Vxs1%xdY9_+#t>$BpfGIf=ww<W=&azS_PCkWfl2M{?N+H%;Lq0?6H_yvowKAT*87GQh!D)I9*1t-KroUZ4v'
    'o1~uV({r$AqhsUFsIsB1|4yAB>7?n@o{2F1dVA=)&+%AixMBj9jp07iFib3=lvmI^mGPe%A0<fPYUhAofOJnA&`EN69PSy`sRKN2'
    '4v6<O%Gg`A=U0_Z<MW9*^ITLcnY2X<p8AlE)9xeEi=~O}U;x3b1p?4AvKmc9=nEwE^JbJ7Qin5`04O9K2T_qr2uoAxEjuUf*-heD'
    '^E>+uphfl=*oy2#W0dc$kgRRRZm;(W8ZqJJd3`5_0gkQVqXOF964vH1{~Dw07(*}ztq51x;tX2J2uWg?e*hMJg!;>HLS~5^UK`ut'
    'tf}{QaQF1Vq)Qcj*$#WoG3;`C7OdmfyoIR37~XJU^<}x%g>^)z<EFRaojPV8_vKBFHOqw+^ONrJ_CQmIISjxgyVPobz+SGue;4$B'
    'wL=w56EnLR$8S`IQCC2nxR)AV^lg}3J82~!3vO*5&$zD=bfUq$J#0>12vcmkZ*z?NVhE!^lF1se{vtCsyeDBza)~+dZAce0@M%h`'
    'h!eA=TlNu4b7y%+&>-B}nY4&=Ngc9-dOVq!STb1|QH<X~m!_$L!7AoBv4wq{)L?c?=rINi5OH<&VvE~|#d9Smpc6D>?_sCt5Jv1p'
    '>j##s0lk@Ngd1F1GqO&7yR6p2`k=BIYHWhp*i{?#e#`J`5v$-e9$FUQVE111+w+F_x#TIgI4jn_3SLWL@E+Jdk17LhOV3F`=^$eU'
    'wlE{)DMksNEQ&uW(s`;4&l>hb=q=E(wganhn046I2Pf|6U0c1|CW&E@_a8FmwZl2L`NX2siesJX%NU0QV;JV=`UK3A#ro&KdoB$2'
    'gRptvxd{5P2g4Y@xXG<kC3c&(C3vou1W%&8v*+9vAboK3>k3_o<=!+0pv}Di#EbWEw<d89-N~rDm_}(AO^r-u_UP>|y-}-Sijt@R'
    'q)VWAGU*|fZinu7ykcenf__?k2$wP)M=-<IQYK==GN;<R3-_D`)%WJ&d}xyhW+!3VHkjxJZnMBOTnwZAKtf2<Aaewqs|$HhFBwK='
    '63OU8lvphDhOC)Lyx&nmaQAU?>63ME5ZS{v&H?@X2h~75mNCmanNc>0=?fl9=KG3jU+<34(f{swq?OC1Z7w6TI}*;2#s4%|dc(%K'
    '5Y-iKXe;GGt5Y!XLZjwI(@xp0zR^ki)~xpx4KK@P$*^=CoNh8<2kagS`68D;AghjHkwx>OS$j`|_*DmdFFXg|Yl1humka-13xd4u'
    'U=UKU>juGy6z<gt7zYE>ph>h#IQD4$qNPWUi9qta7Qz5nBq9*#!Yp?fjB?`6b1vHv4APi&r|$=TdDqBoF4r2jIwgX9C68rLI|~pq'
    '4GDmLcl?htx){wc|ARr$@bUbl-te?{&&I|Sx^xI>pVrc})jsGR+$&iH#G9{mQiEZKTsMV|gn8Yd<vVFT8u+d_?(>n;8+v*Sw0x@u'
    '`D!>rb#FrFgD3&O+>N5pbucK$F?>6$I|B7CYdnIU3*kz=01^0}#%VNVGvb9mL8m<=wp1zr#{dyNIiu~0%n3-aedATG5=EXl3xXOk'
    'Luk_$d+~80&Iol)%aDz2Vdt<8G;%~nPrAYE6sUU@M2|&n5ui>t+lkoTF^U9|p$w1NB5L2~!KAqXK6?sD0!k)=w$X)&NO-o|gD^Lm'
    '>Arg!L0v*8;}Gp@9YscA1G8P`llup)^=d*kGMyaK-+KM!r`}Nlt{!C3TuP{MwF};2_^BqK^Z+rWIcZ?$AQ4%VgtDNX{kqm#R(%`R'
    'U+DBJt(9cQ7N4mw#~1W_z;5P^<44oE!O?Ic7E{T{tigo86M4D0C=EL}yNPr+!o0>Pt8e{%JS*i~#o&D|{MtDm{eOg_NQrO>Pu2HQ'
    '|7Yj_7DY{6jqmTuGyJ`>4Y6~*<(fZ2N5JqAFoXmQBY}XDAj}cQ@&wEH%0L7i1Hg#|O_5i&x`;5N8RKAL3O&U!UNSGRzn*^}0UG7Y'
    'I@Qz8{WWB3FobXUL$n+(+4eg>V$u2*FcA5It~Y;k!V?Q5mR+FD%HLeSq4|tKFm!D#oPs@bbe{cf)ZQl+M`zO=$E?76)^yhR>$5ek'
    '+|ujLaige|uLVGOKHG)~+v+=ZcpZg<NKuzf=A3XEw_+AX@7Gd%MrRh2twxa+{80m}qPFb&jR36>6`@MCI#ZtTNwq+pxpx(%apjfW'
    'lql%7q$*kuF;5S0zTV0K$j(4159PijoT4WMADMz{?7uZPJ+1&uxiJyfL7(d%nD!49v575eJVLhov1m{@tbF;Y;Nz>MFk>qmKq|F)'
    'A!MQuwr>zT6GL2i!SgQ#Ej9AM3i+O1QQ*Z}3}~WAb{19STf=;A(y6fL4ZO<LN#+{EWoJ?RoMkUKE|T&Go!!Th14QU>YkdnX&urs*'
    '*FRZYeur@o!kSBBi%c)Sik5)NeWXv@PpZ8e33jA@iuHxurS;zv7w46r{%*u!rdX<*^)_;7VYi#Fn3JB$y@?0I^uLqhYC|HVJHQ)!'
    'UcL8b5V>Ffdk26+$TGFM`G(dE56mx#;)C;fH~hvFYY&$6s$^1B*vl_0A&c#IZYu1zhMwGp!?zoiTEQ|-%jm_shsw~4+uZUvmv3bZ'
    'D+@|et&SD-oyc_@$~Eu7{VHF8&Wpp~UfxjY?Mdjst$<0~Fqp^nWMv0#IVio2L!d1;#q*9Fd9DMd<)kEgqXa9s_As2Ah|izP%9Z&0'
    '<Qt`ic>Kr<9Z>4^36w4*m89G0-+dP-9&n~*#$N?0)tSej+>DQ9#tJ^(t&5rE5^lL=3;D6SC+k-&&fz@FI2UkPqMF~(1JCWTa-}?6'
    'cw5c|KQM@E0BcbWjzn~Sdnc%u&w(!3(uLnuAqZ!FCOL+W$}3AU2ECG`>2D9gL~bC2d{MUJnqvzZxpED`j<c}GUyfWuD?AqVSxLJ%'
    'ab__xI)n4e;>qqAOF2q(b1qO}X48?+Sn~TqyX$Pur>j28$jD6=d%XCZ-Wn!+-8btMFB~1Hq@l0%f{0-4s}&<Dt;Dyf6u_vIxZ<T;'
    '!u09W_4sgcZI!(6^0x3t+4i~bc|FpRZ%A;OPk&FGSO|BW7;Md!S$ygy2d=Ht7sq*z-)m~`dsTXc=~MQxl!=`_P$A0LO2y2lb+FKU'
    'K2sM9k8BYY*ZAbe7G1jz<d_>5?QFuwMQ+bIcJ100`mwAPV98~Ex;q3c^TX#Aeqh9G1t0BiHP^?wbm#2C!Wt^RFH2I8yKk3WmfH)|'
    '3a`w}O@`5YriD%1&e!=vU>kRAXx?izSFSUx<1A(%INEbf^@^`dd3;|2eQ%X!v=%}EH!;WVIQ@}$&blRx2uHqT{<D>AeaN;7(h7>6'
    'G4GS6e3-w!d^CRRN1ro0A(Zd!`mg~0;09w?Xtk<v)w!C>a)`d`48tm%JEj)t`Ezv<z6UPioZ6>+t0&&_?90t@D2zY&a>f{Xa3>ag'
    'K7r8D5<<(hT@X;Vb8Uul5u=K@uCV3Zt)m<h?RI@u>GnEsap`UldA|7^iM-<7yZpc6Cfk>r&;KiKY#+iz8^kw$#2iYxY)G{48~35|'
    'W<V!t8Cm|J?}-l;IX+}S=xUc_U;TRde4?#IGZvDsxv;bPnd_76x*|sG;D4jy!wFI+HSqu9(r)L~iVr9IuTQq`ru5VF?U??#&{eGW'
    '^2xlt+#<`esi4CmgNwEkM2HWSk{mUJo2hWcN<Mn8P(a56H*e+!uy796nMi<?r{_07Y2pe`C1)UqeWAOO=k*-dAf-a6^8hyO7OOrU'
    '4@J;B9`3dR)i-+euEU_iaKAk`--Vzh(D*h?dX#N->bko~zPOji3;CnPpgiI{GdwnpxOew{gs>hzPsml&j?3qlKe`uB;Bij=ezlKu'
    'tUWgx4$v_^&Kw?lkUnyx<##8X*u*AWxC2{QCN~Gpq9et@d*-WxhoXm$*vqZQiU+NK3c||q$<t!WdSRuk_yd>Nf<I(%zfjC75XI@!'
    'RYR>y?gHJ1dv~%q#iV%j^)YdK$GF%<ftAOxp`=D}OVe8_OF*)b6W-LCn<ns19I3KbCf9@gT-+kBZ&_kc+LZV8S%40^bMcwpgq4m@'
    'v3p)VjBiH$FE{uKoZxEml@P8GUrDIcVwHy9GT2+JdGftCyH809yARt&(h=P1bQGfW^1sIk$BUtAzvA)9t%d77`0^>gd$e$tykH43'
    '`D6WmJjUNodDH!`MG^HV7e)NytzRFiw`RE-mR@MJM3z8`breOdx8`P`j54$$s1-+XmDI|E-~e}KvEv;iYswD!-(DZ<E!?*t|Cg2c'
    '*|TTA$(Ox5RkrKu>ORT;>#IC|_hBgwXy&(>{+dSs1-~i0UueLq%SiSkJh&|&@q7I)RFi*1uP<rpRB2s&jYip{;qyF0>Ycs!-<a}U'
    'SYFYWRWi(8Qbuh$c~~V1s_gQeNTgUr_1d@2zwF_^E@)&X@cmKNkwxk5hlHvl_kBCS*6&oiavxDyHr2LsP3v(xsW$EHiiK~cQEhT$'
    '!jXu{tTyGt`^kJwul&0nUxV|hz-pfmvB$EW-!4>g%IfhI>yNwn%4EmyP56rT+sG(Z0o#g9zM@gY@fBE3T`sY^|LtX{G35q`U%a#Y'
    'flezHH+3avzl5902wtK+Kfk_QT|{65dfcDQ8Q82s&MAaTz^iVngJeVAw`YMh8AyD;H;?tm>`Po9)<Io3S624m+&Xect)^e8?94Dl'
    '{>)!Y3&FjdHEf>|-!Px@JnfdOVXHaY#cZ1Ea%b)MhLvT{V#$kjxcH_Obj~8gJA1j9sg7ljbwSnbIad+KXVp4awt6hnJ({L{d8))l'
    '>s4fJ*48OrT&(c$oDV|f=6il%w{yM%s0XXEL(R()1+dx3E#@oAH%l5q-?ZY=+__M*Bzx%Kq-XWJ3u!-Ue)<wHmRP-RN#D6|fh0$0'
    '4oMS`RcFp__Pao<Nr{y`lpXJue!M)9Wg8*ig%OkO=<#~++g|$Xawy}!t`z^H%0Lzd{Q661OrcJ7Kc@qvmT$MtAS`RJ?^(%JY;Ni|'
    'WT@1?q*zm2`H|dWgYsa2fO11P`xM|&GA);G-ICIn)cj^^Q%*L&Q%R?pN_bZ3C#GoADf^Dh(ZdIH>Uo?QT)X{TP1s#tB7ww@lKIGv'
    '<ecVO!`lRC!P%*OpZR^BDX}fDk96Z2UfVs6>w|>g@zU22ob5`6ku}`WQ!u|YkwmsG+*c_wz~4wSuKbxB4oanz9d|0d;2H#wvmXp<'
    '7he!T)3V*c6cq*>D=L_X(uI%WExPdX**#@Sayxehw+8fHT@i~iKNtpbJ@AyuJ&s&|;-OsBAEyGO6rzmD_3g_@P*O@t3Nt-?FXvsa'
    '@`ZR{zbpk@UK9DZJ)Ap1$Fmz`fr$P}7f)w-gX<NaM=%v7eK2LKhL7O6QzQ5|wN@N=*NPi!XoY;^@Bgh#=)5c(on2RuE|w`lcg_Md'
    '$!3=4jY1a=)y8);gbfhZtc*sX5ZLwi|0ZKOt9+I`^iVlj#u}H;EpLnie-;u0p*Hg8L%tX|lEdtEmwzJN>Pp!*Z$m{JP)fxKYh2Xp'
    'Z!cQ&<nuXGX#L8&#Yf&okbMXAPrQHjH6PrOTfU!<7<}&9(szbUZ<HP!^D@ee=XT|VUs}mAO*5{j{|3(9j0*tC=Oi=A;P>nr9s}jl'
    'vv{nRJ-5b!bItm6KppyKf4(&q3`-K)pZI7zpU))dz{lHPz$aa<Q<~T=_H%O>bnWwvae`zfl@*Jg7fCs3!-_L)k8{%b+$fY!r5o__'
    'rkr#E{_4v~n^vA_8;@tMe)DV@!olF{Uox73Nolz8g;Ydf{qZTr4tzB91>8_IH8pYFvLogv?yADb+%H#qP;{hE63DyXj3vubGAO)M'
    '7YSrK{Q7Ir^Oq|)mxdL|?M_m2#y}s1=8Wc>lhl!#v+DJ;joccsK?5UvTlMhQU-K5gkA1l{@$*RyGw#{cUECrwWbNv5JL#Av7xcSA'
    't*Z%s|NLS1#DgHK|KeYLF}JGq_dE4}Y{f>1_}BuAWtF4xSNt~*+R1%AO@*%wica+0C$}VY<{WD1#@~Hfb9R}Zw~To4v=?6UXx#P6'
    '!;`+GV$~lu;J~LoXAfJ-bwpAB@2jo3b$s^}{=@EpPU)ZWZAAL-GulbHnR5}fDwQNSPztaoH|Up2=_&p97u&iclInD!<o;58f>*}p'
    'qX^8e`fuXw%(y_rbiV}VwPxIotWQxI)q4)+KYMAzxilzGY8S^z=OHjK*zCpw!x$bI65F0+u=#Wy57SNLMQcu)hc|v@*V&B1YMT*_'
    'V|T9lf^|>6WcNT!x6Jh9B_wbs#^@q8bNa}YkvyT??F45y`SrkhJHP9y?tWEv3-QV+KO%aWjktZaHSrB(|H>5?%pj=rbYE^B&8nY^'
    '7M!#j;_AVi)Sx_f#A(hE*1mf*iu1VqQUtv@8(Xd&N-d^Mk+j{&0=RLmE@gLi_`00ZFq(6P%n9ipODp>_7$$O2c&DCl^a}VqC<NOw'
    'RajG|l)av-A9J3lMECL*_b2DO5_JiEBia{QNgg5RN{++4k_r;6oDg@npkVu(kT2QyrMXhhtsW$fxBLF_3eo&DZYfj2-FjIQbe{cL'
    '?{g^Z`q~UObA!)*RKXd!au%|Uu9YU5pSQ#1G-TxO>s8<tBe+$RUP|fJbGAashmw~W^vQa!Pgei@fsD>mzA3G?ZF5WNQOeL20ETZf'
    'k%Gj~O0W^!!Hym4x$v3I>s+f`iWFsj4X~x4_jX(@&`bWL0@o^LVUJ|LMk&{x!q~H;%eZ-3?21~P&EI}f%61_pkEJ+()?5=}!kPk%'
    ';%t;bbQFPN0OxIh`<nAdO%8F!kn%MIU_w#xA*<1|ri~l3@AbQxzsCIy&V7D33LvtmQzX*f9De10F7phfH0Q+oU1nZ%qIXP~wJRRe'
    'b=upBq`dhYuA*|Z&=V%_l3cQw87R)OP>p-E?e}D+QRYGfj33C@+DhhMDoN%w^oGy-RUO;-?DLsA(Dk*8MHyT3Cb@eVj1!8Ve!B*~'
    'C>1}u279=v4yDg(ncptmH{mrov+VvvBEQ*pW<!Yff&Yt}{d+1k_!{#ha=OW{keEuTSwZC?3twP;Ss}~9za~h{zPrHTES2`J>&uDZ'
    '@BX1t;fY3f#9*_0%5%9--M>eieK|NO_a*+<ID%)WEbF(W?T1h{ijnHuDr~=nn+v`4??Wq2+Ln|47)yzBG2=Fa>wLBRpES|OEn8g|'
    'OJ0KgYB1z>1aL-mxg8;#(O+{yMqH2|SJ#N!>4$T4)jD`C5??nPANx1_Q~L+6#`<tvYWw_GRaT>89KhXN?8}Jib(7;CULfK+`(ak('
    'm#(!d*$}00?+S(h^k)nzByq(B$TVw}hx0E|IzQ;k5HLLa;g!n|I=BBaKkwT4pmQ74azKP=on>A&x(nVT&lx%Nj{CLUNqZwXYz!PC'
    'a)Xn+MsTZWdK+Nr5(d_?0Z)Ko{Ui(-*dj)&ck))+ekIo_woQ7}n045ftlkr|@7SUwY}@kiu=#qnO?)i}ox69Q1Ux#wOL&wK)IKZ%'
    'e^bl(u(v5if*v<_1Q{|qL`FA`YaJa;ZsI%JJ9g}az1_nDSViT8I+z`ZYyh=SMUpHtaV2Dsba5hlHg<Saejhjjj?<c?k9LP0Lt)-m'
    '6KD`0d30miq;<0wj#GF$!_zh3KzGnb0bp1Fz%*CBq~8#U+=XF64X-hvlC1@s=fc1}(C!HI-vf5@l`m^=9gC94VAvLYzzz=YhE^+G'
    'YgO+#HD;$-IaKyNGvUsagg&x8)8xq)Ydr*!E3C|n6F@f~py7U4G8N)#shxwNj^NW3kWh(soK5WpL&Cr)2VABiHrEe8RF>G(8BzO{'
    'ngb3(-OC{IN<4?7-0eP+KNWu$W}({n%WsR6NB2{7l=dZNjE5l})CQ7S$j87SwG%+|3kY7imq@f)TZp2Yrds6bj0s@5mOoQ6igbsm'
    'cNvb?eo$lOYEXZsp?4xVi(G)U3JJ&hB;t3MAdiutd`=&~?dAY}yB#}rpGCIAdgm7@DcfKubF`m!`{b3;V9*F^KW0kgY~wDyuq#BS'
    '$>-8grkr^ub2%6t6)AUy8L|5>P6C?)pj9B5?}+bi(Bh(4Cr<=xlhQ`O3~cOY@|PPx)-t7wgtMkI4FmJQ&}2@Vtthyb+QFDV$HQbl'
    's8Imz6STW0f%@_I?1^Br4wUZJSib=z1vPYz#QeDs#KC9N+QOt=(Eb8A%mpZtObvkg6}rk%31Ro3Za-)d1KJ5^;_9)nlcS(~s8yg4'
    ')dxqJ&5|BrgS4y@-Rgt%Bw1c`mL<C~V$eHW$X_=z0k=Ls*ZFO>KT|xn3OF^De27f4r$a0MGc(m@2UaCDQ9E!sXDzJS3d*-kBub!~'
    'TN9xESt4R56;e9nGaPETeQ$86w;saWVR9C0c@)X5zEymv`z(jnwL_XEis5Y26@A(|jB|%3H{p<uez^Ym$i*?C2!Z}YJk`i*sce5>'
    '-`-GW%9&llFnG!uGBQ}iXk5jq?>7K;3<8aZiHYZ8;16=~%C4PBNN>Yh^Wv0qncbMr#falnsMtG$`TN9kIepm98V@w7(0HzeXQpK0'
    '>~0Z%A$y;WR(=<}Tslz*?Z`9jQ+XG6ohN+(W^4nCvsW^Mb?~~><iYG_^=@=#&K*;Bv7*bLteDPz8Rd4wGtXy?2J;W;xT&*af;R{j'
    '`1F(=@WW1arUfgu@cV>s+GA5~k8s7Q3zrWYg6>1?wRwRsO$ZKSi|vogELEGqmbT}r={)WY(DkV@v^<rW9oL4x+GEiV#mCId%x8;!'
    'd8`%!-%lTa^f$x`$Num&Ai5V^ZPxK}raOC(b*u!78F9+^YwVxM?U)zcAePMhs(8N*dlNP4B|Njv{kA{9<1fBHuwJU{LD|4u%&$<m'
    '^BXSa2QR2Yh=YrHl+85tWGgI<{+zsmN;sBiz)GtVfMq4JYAY9+r)DToanODZ6;Ude>rnyyj;^2rBH~$L_<j*}a(1`@=soO!oqQ4I'
    'Fz=b`E&0XB#|O@5?vFQ`)p~-6ZZ;CZc4srP!fMhGr(PM$+Fa|oGHd!RBP_)IZxBSD+12oe;im^(l|5)7K8TqRZ^#}rU?F1|uQxS#'
    'iX?e@5<sWqjI2;*?CvEC?-zJs7=x_~hib69`mqtzKQjuSm|QxYJ?a?WsOI-n*(m`VVBOgh7p<VlC2Z*)&@Y_8Ot>urb2BFJ?9{Wm'
    'mfI;cOI;P8i)Yj3z^?TCC+UY!-e4H$ufBVdhx108UlyH-wRc;pRah6aZnT8~7t^lHfmC9oy_ZhKK~;XFqx!H0jN1#~H3v@O1Z|dP'
    '%)(40ZD*YHq>m^9<}^dpgP7xFf7fNu=(0bkJXh{<5*E+TguX{W@>u1lX-p$`M6(A5X2ZgTR}h^{KOP8;PtcueeMjm|;$@EuO3?I%'
    'CO9~VsRfdAVJuwt)N(>%wXQH{^W($7-x`+UaM!rrbRBibO*2VW2XM9nXp`A0iwKR|OU5oW;iF+F7JU(DUy%1pgB-+;D(Mu{%!h1w'
    'R%Bail0%f`;3GUKWa#acLwCS0KDSq<iNLo#jMxYoIQ*w-!m24?7Vi667czhGq5Xdp8Umad>I_3SL6XJ^1DL(|H-REqEX3vAE{MVE'
    '7b2m_=@>pNO3P$u7Qg2}Cb%yFt4q*3Cv3@WD=X%9C49$+rP+X0GAKV)vqC}ZYF(=YP=2C1F)k!!1*k_IOSD`_DBF{svXH!2)T58{'
    '`BQlERsecu4>%RT3MsUF3fpFYq!3n1q0LjMof6}k2dev{6UM^=Cs4mH_Pi7u8>=&)Dd1JZ4;^*@$;BPU84&o&sct&RKQ+%pIpx91'
    'jnEfwI0e)SVeJO!^AwEI4s0j@<H1lb3$)@+Cie$RHn}Z**?0WzOk1!_2K9Wlzo6Rp;C1xIvOo5db%Ek%($<zYM^)<_FW6;`-#eCI'
    '{l!Bh)K<Qo)75DIqP+^Yqrb67_hhaJ&KY5O3Pz_v|8UD4&^Hu1#{O82JrY9AOd@9F=Vq!$9Xc}|tUW;W2?bJwt0oKGK<%-TT4c<b'
    'i7@FX8?1CTSiZ8sDpa*fputjXIgW|vqaVklEse<`?}wl`dgG(cH?~ATwM533+CcvniAPhLuX2|(Z=vpx7~60_J(%IwC;8Cn?)v*-'
    '-@^qxBLF`=4ubK+b(1|nsQ?te#{@we1d6OE`&*FF6wK0*O>>{EbzPFH0ihf4DZR>Y(&ehEf9y^PXMFn&3zKT50}OH9*(!e2CY)?%'
    '6X8%O36e2;U@@|6%N@bf8V)UqChr|{P&#dSM&h;zR=J#S1x+qa@&%_^O1EodtAj%@PIDv571IJSz}oXDPYjKXeS<8r<)0F0byXMi'
    'vReXd%ZrVj2zH4ka8Vy1Qw?h8ieWFsw7M!`zabsb^qNGIx+mdxAD<NDY*Gvmks%-DPrU9`V>sB1|D9M1yb|!)$0H0?dJTlS(WibT'
    '7LU4^g$O3Su>?84Ya~6ad3P`r#jx8Xiq%1Z#>zbOZpwuVx`si!jc0W3G2JL=*U#RB*P4K?ES}_0ex==lk^c-20CXk~TL`K7&(8lf'
    'Hn>Z+b7SPaw0+0}*5o>w@jM&L<HP>t{D*BT8?lfanz_|JU>Bx>QuI2r^Sx!gbu>6*BaBQ1^#T|fM3Afa4Le(f*Omo6+X3*j+V_x9'
    'XkG-`7o(-OAeOe-iai)B-+rkT7(3Ii>eu95Cd(9@RSewrk9+^a1tAkYOtJXU%G2|86r}*v?eRt-Nn(U0*xJI#2!N62Q)AR5dD^hF'
    '_0FPD?2u+`echJgP!ex%)PqHBp=)YNton442>Sn;CJdJ+CCoS?(@@FtC7$QFgMt!><M^1kNhHJ*%jwT~QZiI*vm5EAH<SKiJ-3Yf'
    'vlft+awcg^1y2$PqVw2SMF~9QjNroyxXx+7)BBKK4shox{P_<4gRQ|gRX9t0!uT8zy(iZjw>{7lcg_}+Oh&4;J`AYkAN+r4dk=t|'
    'zwdGUJWqQUA%u{<-?GQs-XnYO6|ytlW|UE8LPcmv2q8r!A&Ekn*`Y<zkcP(jpL1W&W4*2S=lA_T_1t@2<GHW<y5p>S&bh`is9d5A'
    '!F+Fz#{jQ7u;xX4!iaP%H<^-PLPIdA9oVx#P`*S5f+bfMXd-FSI$z2uNn9lZ^ZZP=TTjp$W}sbD_ttOSU>csWkmAH=WA?pqY(d@p'
    'aw%epv}a)SMHC?+o4TvKLgTf`-I}_qCKsvqD}C>O_d0KUJmlJk!aKIw(ml#(HKMUqcc;JMrOb-iD|rcXk}!Qc{D_1&ry`ji+Cn$6'
    'QZEixt3ML4P)FdTx!848mXOrsP8n&oHS%W<c$6D1Z7CWQtDhC{SBi)mIJCr~8BT;FjMa5t?*ehao4svKGXU*(XWFJxiH(ZbT%q@)'
    '+>pwWm0OgAmYS6w9{Bp6!pgTb1Q#d<$^tvZrp-qAn7^)U97k+RMVt*IX*B4($s7CnLz{~Q2GA4TpkrY!GH1^#<I9kTjMmeVT{dru'
    'N<JLy2sMwT<wvybdHrp_CKw4dF&HY~QP9Q%zZn#h@C4|-DX0cBxpl8%H_#|7)`dFwk_05)Vz?D2wfRuJfG*H2-C2E3FRS~eusV<1'
    'fB>98qpL8DuKMzL?!~(#>z5Qz)4xJO*zwqkla_o~3-tIxPrk($XF&DBH@XlYZCDm}24HZ9@I$@3+{EHyJg#kzI7Q9;oqueCf$4ek'
    '?!Lc|^}VpTxdhmt#n*sxh}Z4l<8u>(e0(bY`yQU)KGnY|E|-X5F4l!gr9@c|(?ms_I*6pg0pCBj7|q2O?x$0~6o+u*IdD4>=H5pI'
    'K<r03s1-!f48c9z>eF};g`Rq)h<(O1_q@qt|20>PKaDRn^$N3f;3SUx8zb0kz<D%v5=_8=X}o*uXgohwIzIU~x8h>lp_BhX7tZ1!'
    '*p7G4<3m+Ycgn~MGNU;$Jq1}geHXJt9@@ngcPMNU|3j|1X;UP|Y+7X~HDU(T@PC^V)g3gS;H}`&!iF8P9;kpPN--XG3xfivo5MB>'
    '&?p5NC3MI_Pon%5ACQTgPNEd>dp6?PfPjFtE0xHl&Iu~F7nDiHYhn1Q*`Rl!0LP@Q;o&roGVqKlIixC-<Bw;vdxuv2D6w<~Fb2bI'
    '(mmKX{%GTTyndk+`$31$cOPP<kk_G@q*!c_0K>Gi65#rwsQ_A+E;MF9H9k&N0E<a57C@w8@N~1<v}uzQ=7`Olq)T6bG;zyN$SbCs'
    'HZ@d52}hSjMaVi#4*u|Do~$Y2{g4uzQg-M773$h+k^?j*jd(-+)Dny={}!(Wmy`~G#(^1Gk*q$jd6CC4l$T)2>5^;{jjY0Iu;+1~'
    'ju;|^kig@|^PbO#`B)mhCl3eD!pCwN&&LK}IGa{nDqECO7S<3NaK>lHi%Ob<>W1WxF}(;uO8fBsP3<3W1Eq}=!b_S-O(fJN+DV1N'
    'y>YRyC<Q{u!m^}0N{-oVkR*PD)1|dA6pG)!f-^qenGOc;aPOLTIIJDpcWpxFGMOJ6>4)KHX!ZoLU^b`(qo>{b^v1*30%s-$tY%Er'
    '6CX?@>_y`u*eC@L*}ud7Q1@iohZtg{%#Njg46O&+&+x_tOx7KYcjbgPrY~f)H5WZc@tUU-UNC%z=e$2rA+2NbZmv`8@N12`%<e?X'
    'RIcFwh{MR67$b)oLD^Y8<#?0#EsEqvpD$Op@I=^xKM5P7xXQf5nb|zt6|9o(q)UVVWnH{JVydZ$-Anv*a)2sfqkD@)#Ds}>cY)Aq'
    'S6KT33;p}>3azZOXD%jH{_5vS&7@)&ns-oaeei`<ZSNs{%74D+-&Gvt-%m0h?wN~eTg6@(dQ+niZ_O26t92Yw7*7Gz+Q@*;MB-;+'
    'tu?#nVCt3z($7`CD^Yj-lf387WjMHh`svqrNnSfQqdXX9qGG+}9!hJJ{qem}piKOfBN(errEevk$p<HXS7fa41o;{ObI16s4-Xs_'
    '5v1q7-_fRmaR<*#QPSe)ikOvCGN>7weEbV~-OP)aaTCH95#IHLuJ3zk%+1{aHhusZJ>fcG3N;)8lh1)3R@Y<N)R_3IweC<EjVtk<'
    'b}lI(zdr<2iY#QQc4g+oyfAXUM!bKpBXoQG;eheY9AD<-|ITakO|7kSH?^oxtMlqRJrqXS9*Kpy5B4d!NP_}={J9Tvlsj7o<9w8Y'
    'pp-3&)yR_2#0<27gVNe*cxe@yYs?;)NZTSL$#|qkQ8(Ymj!cMKiUM~-)zWt?pH#*-DmExZ4R}C=T*B2?M+j_r+<kvIvfsb7X?-B$'
    'VFqQ@6WCH*8Z|l7#l1&dU61Ey_fy{61JhL$pgv+X1=tIV^hCMtC-ND^ivn`v=kOS-=9XBPadj%yw?PJGU%64jyFx@^7|DFKABL5$'
    'g{8GWFQ}y{8*u`D_6M`XbR}2?@w47N1fytLRf-NY2eTy1jf^bB^Yr2sc04W2jGn6^)gk-ZJT>taAt&OB@QRk=Ei6))1(&Km9^cCq'
    'pb27i1t>4YMhdVp@xltw3KL}#SSy7I9F^-IT7Vq8grD{?Zh`7oOSNX=I)BP3elIQLHvD!;*B_MkErOri_XU#5>-G5=)=J1-dC}_2'
    '{a*p%Ghca6-yh!dQvfPCJub+;vySI&oi~_!EwTXb>#+GqBq1)7=&%;VV}8Dwy73Ks+mDfgo?9Y^(6ez3Ah?<o2n*U1OhhB5BKy)Y'
    'Tq}+GGMvN#_Gz!U^J!sr?7DKFD>D-B{ShdA1Q<^o+LJ&0+0Vc~{gN1@@X&J)_@MCAOZdb53HDl@xDCn`pm|>`z4Vev`uO;d$@|MH'
    'sv|puvHB9Y8}BL3+T+uTQtK?l*Je_$Z7o%7iYppnn*u!BsX(&7;GfOK_tlh*dJ3<rDZnzX8O2C%(xI3t_Me8yp8;Y3E>reVAOWA4'
    'lXpaxh3O14X!oUq<U%6nW|$})T+C1*UcgTrr2m8MA?U+Gagfmj9klXKSW5@+@=hO|s65zJ>QhoqdC&ukuY&SGJ%?CH<pJ@P^%Vyg'
    'DlmaGjJheoT#S_|z{FEHOaZ=aQ1Vz+0yDr1XDC6l!sKcSkXS8SC0IT;vs3}Hdw~)p?uezq^4p#iWM2_cnyM$^$EXLT$Z;6LFq$S='
    'pM2t$%oONvCtiX<C~ZvG7jr)&OAAE#KrzXf%w|C4QWSfGI8!qd$INcZy$i4pp|ls6bAieid`{WTPYN@_ER_SM<fV_9)K8~V@wuMV'
    'b$Tfzf=Znjf=eaH@C{LA#9+VUDfm!R>d<r+rGAIQJ|l{9TM4aP78_|)dxamb#+C}^@|<|%&ILr9tD>||(Jp~Lq&Mz|*~}^_-&kd^'
    'f<E-ckK95{B@Qf-6)qRGiJi{H$%IzkV(O90pD>tdqv?L)&r@xcTT0x(rC*tPlmz=I9jmMp^PVUO34XZE6if`?%cZzl`5xAoss#VS'
    'PfBnh-d5auskFGS5+S{7rFi|a?{JW^C1zlfz5<lTuv?r|Ld(*UHlVfaPIhj>dQILJ>BTO$4B~DzOW07bappA*wPIA7%^bzj*v<V|'
    'd!n@=nI4oWF;ewsUdK-g#i0Bqj_?2A3KgaK6bF}mg~`W`zQ!loP<iL$+)vMTRUrOM@!96@{{UZ0>N#8VQ+loa9{@yO4TYv7<9`J!'
    'pxDfyD-8uLsi7w0Lm)POzZ?wXS(xrqf{#NpFojv>&LLSvul82r5hZp|SdO6+P=v<6ic|FS*$=mDNud#(V4-C!o9_(c#E;!fv~oUb'
    's%8q~25;>1Hy)9OnDa)_b)c5<@J5zoo92ea9!i5RWNVY>Y{Ax=6*o{DKWTfgKifQHE2dE-;!S2T#JBj>Gu8n*fH|XpXAk_bJVYQ3'
    'm1L}LjGilTfGoSjfa@}>FV60X8|v_oBK+sL7MmNDhK>>YXEnm`Gx=)pC~b#ekY(?(US9=5L=U80n@<rf5OTHT-na-^t4LFZCs}8F'
    'PfT)|cf<vHFvsS?e28&INwcOUY_dr+EHY9dYhR=S)Rn%AQaJePd3m`df`FgJHOuh2jLn{&YpOrODWI3cJY-LNYv?5WV@NP_rU}6j'
    '1#aSEl{j3$jyiW$Nyh$A#q>idTiWksy^%05G<r)DrJRCyPzaM?h)NT*KZ8E=J1oxzp~Bm2D+Y@g5IsuY2w}-M75gZZ36ja<Y`iO^'
    'p9cB)0!L}w5%#gHoh{;$0@iL(lpI!<lDN8<ICW56jAfI$|CGG68Y&8iC{$<BxfyezQ&{}i1)$1$A)z6HeJnc(r>C}zs&z`(#XaG@'
    '@BywnXzDW-(W3ujGSuoh))fU1;rWQt+WH*y7XFfO|5~|1R=;<|N#K`Fga2@rHVu^-P_B@d+aJZjGC_hCVY~mPZZ_Vf_;ep7JRz5{'
    '&I{~>-RXb$G&=h(m$#eLe1j{k3$n_Bnt3BoiD2dKyhope%4Gn)Y+o&kfc1C)46}$<Psa2WG57IkEwzJLZ*8mHeK!Vj(Nw9^`!~=n'
    's^D=?2JWpnirM-EjA8M0JOO5m4OSCCNca%0Ab{AFhd2^G;-lrq@U0dUW2f7NcQ^v-p49wXgrWU0bV*7{_qv#^1rzeThvE$>KpV!0'
    'ya9gDfqn&HG)pcnPQ-Db@A{_ju5yhzOIfRLfI628o(#$);1)(KjVnaczc5!98X}qw6Ig=YWw^j|AJMc0U;2wK$sW+n@p)JUn#2}9'
    '?E3<1fziG<h4KA(4(}Lsr?_@wd;-u7ca2bt@nQIgos&B@!VGnVkQ!(mo-+-~9?U3wv`7Z!F66z}fK_<YN`>&pKZ<n$&At(Me5wk#'
    '3iR>ov|ePvvtbX>oQCw}rFU|%YIFRkPxIi%Z}L$On(&+4$15xD<kR~%j`@@@;2qC-JsB94=E`Jocz8w_>!NC(OwWI`S`&WV)h#aM'
    '-RsQ2O^;Yi(;#3D=;qQ~$YpiFJsRcW<~ZUue*>(t*Z*Ajuf9@GuCUktx`+QD$;HZ5_h6xV>rWZ8e)CeMuo_Rw85mi5Rg2FIFL+o+'
    'T>2>VuLJ}qm$Z~_9*evR%fE_bGkpgBD#@wz+ZXxzTU1mhHZNFzQF_`u?y4*MGcoA)aV)7xS0@p&&ozXbG)Z!)qx)erQ?(i5cfA<@'
    '_@LFF9uyT-kvi-nUi(*v)%x=e)7<dl(;F|sJtr}C$tirS*$6)xv7Th?ct+4f5gjKWM?&*LhlZGE2=XU1(NE&_#pm$08fb2OS(M^x'
    '#ESkl*9#u^;QBmTbAq?3%w>nv2bAPub;cE|B&2bOM2lP|L%e#Mi;q|MW4bm0mbVM<cKBs?nn%zKc|i>qOEctlK2~kU)1dz68S>%#'
    '8KRi$mzLh6Gc?yfJsR{@Sy;vof#RaJNjvHHx34ooTdP><P}bq!X_KIg{D+HVDsQqDPmjp#Uj<)^B{vz({?~{4aL@qnXNZ#(Xzo<2'
    '<e2G`Pv8=m9rq#c;Zhk9v(^BcDPb~nZqO^-(38N{@J-U5)dFWHLeJzZKSL~*X38&tQaQ*9&{U;}MgwtTrf>xx?YWyq2(MmL-tCt0'
    'Xnuu>tU+N(<(bUpjU`F1?5BJkV*kdm4s4M2M?#gvqa7T?ZbYD+o9cnxCCy}hvRn!)E|j{mw*~4%mx~QZ3Ueavy9J!gBA#b6$=5S+'
    'wo2yyY$u4Mt98(`6^;+Or=HJlJ;@LM!ODwqfLQJDDZTiRSg~++;e;tjgkPSC`OJM(N9Hh3;RV)&Uz5WM43ZIXm|HtPjhMQ!$sb~b'
    'mk)GDh02}Sx+`3}h6T?&SSh6*k6jItKQ*WN9AJUwq1H)WVKyu(HtCDkS)qRxR9<6MnuQ~Hfn<SNb{0L@tn^ApNw*(byi+3YBd}01'
    'u~kpU)e?jCzKHb(RX5#}Sf=KAS^Lx_7Xbdag3ij7E8pQNNzZ<Z8RVt~A2=eN?jzx<O*6_v;-pJ9+uAM{i)e_v0os%_v<H<u+}Rw;'
    'iZv8t!M0Xr{$6JTo?$K0P2%duKVrrjT8Pmv-6N%Cg!WMO9{08&Mn0KJdrES{|L_ecWgn&<N01#zbtUOi2<m`hJEvzjkzTCXD|83g'
    'gHgQ!@|jgv-jgBfLb7VF03>cap!6YO+8P%=L=!VmwWd|VuKO6dBgLYP4#>wo{BYdx&p4lv_wrL5Nic0%lDznIa&KOUQS3;%8OJJ@'
    '9mXm&O7!82E%%~*C$SO6df`+<9Qf@wRMTVe`up(YrcEbl28iXXkEaP2j!a7)2Q~8g^vSC};0_@%OS6x?dgWDzammT!{;ZB|+tWBI'
    ';N^ybAFVkEIY0Z2Vlkv$?s3JruK7d1xu-?Q`y4ilH^?rrSy=o=2Q+Hc2i4oG%UJ%jNN8ooV?wKH_XyaH+n_=rP1A*#wEXUUJZPrn'
    'my@!%ZbAmXuq?b(3IRA5C6k1zc}wB{muLOIb9;N^rDX(_lVUBe*3)MLl_6ThjH#0sEN0r(aILTE|NqLu5fZQ>sdqgXW^9MgEQ#44'
    'B``mGDy$*lR-QfW$<muN_^P~tDtB(^eO15zD~b(q5#S^CN&E~beYgLQh=W43OYFK*e5`*q$no3H%5OjaO`KU2tqS)oxpB;hmoWR~'
    'y=-~Fyo7m?8h9Q4b-CjnX}5kyxblJ(?B60Vmc<1|4oPSciDTh^{yfF@=Wr_L7U#GeqmpvKTg+|_1FHw}|G8L=BOk6-n?;T3%ZZQ1'
    'k=!d)zQ1QI^MG4e431-`!tV~D&E@RZcErclDJ(kvlJ&UEdNnJ!!B!@cImZ?5EjD7RO|q|vhVl$=IaKa7_B9cb{~?+QmGU3Sp~0up'
    'fCOY`nGTUTDcd!Ewch&MkL=qJPy<W8aY2hg@2`%C#VGy?cSg}8_kTX>$~E{@O?fDpVYw)dI!F~PsH|KclRi$;o%-PW5nwCPbDPV='
    '0~`V9tXRGFeO(UxlFGr#LRI#P8hjTHY$VC-2rM4=pL#K&OsiAGpxlFni{a4I)aa}`oxx@)#FKR9Hc<A48aF@Y-uvjzkRr2m1t@<P'
    'mMoxJpMd>h?+{&Kz_sY=^BdOCxxmD|{uZz*Y3UB?(5Sd5o>iygGO(1xNE+Wt{HWepPuIN<8gJ^Y>pt}%439be_-upErBu3d@+i^D'
    '))!dcvmr{gz!EfL#h#ZwL6ANlwn%2)>!Z{PE!%`jfk7)p1{~FkHFG|FU9t1oR;y-M{-~tdYkM9nQQbvoOSEFE0$n*Ku54p9#-20c'
    'H>2Z%72{SVZ@X%VWJDnQaH4`jj|R@A58Nf4VTUJ)MdJ*@&=z#wpVPTeI@gsrnC9pJnt@nA&2E?*A%ik$g4^tT`O1mVnJ3Z97&7TN'
    'Y68Ii7Qg6+s{5hp>%I^e1*WAdsoJA~!z=K2Ai<UC9GtyIlsK7K^=bzeP~(?Nq(?6OSb@mXLeONx#iB40Zo)u|;6`+A*~bce58n&*'
    'C%ux_gf1V~oI7_3<TKx4U>)d^yYhU<B^or7Ua8dj-8hM;`#I~Cmi8$<?dZ2Bxu-wJUWH*<bDF+61woVSr*XKir~0O*pS@ArX3cMx'
    '%~72PvU1A16Je6agoXO^J}6#9bJQObM(D@$!?TOx2)f?6;i(2X8M~^IMA8qfAuEPB=n3#L8&(lYdsa-;eImTdCJuEj<ivn>hHDM('
    'zi#(qJc)$Lt+Uxl`oMJ@DaEh)!_4U(Mz4bEaYyd?mVt(jBm?aM&2ms)tTxe+Aijs+uy{2xNvyNqW<Ry&@7K<sKND=EfL)DlAA9O&'
    '0PU9(`dbgWWuTqVnd&$dlSH6$E6-c-lGRAss7pLTLaExy9#E;^HjKLHdH;++Dg)S6AM~G#%+-;zjvjp})4XcjkFpI1`mM#?#?o3q'
    'H?i1a1&U0U&rJp0o7UFW^+8wC>}%ilxPMj<uIeRHr1jVNvf4UCYO=s)0Msb;g&~){;(Vw>D+Qj9TnX}<;ZWI~Fc~pqRbe^CJ-y!s'
    '9C46d&Qn;5V;~yKSQ7IZg*xh~Cm@OBl{RtbuGRx7Ok>SX!PeFev0zH$WT&WExpbjPu@|#ZFH?kVSt9h^8mYoB*y@weg)h1r9#);E'
    '*m|9kQ^bzhz{dwrG1I#dZUAsdk4~;mvtx|x#ZB0Vo!}CxPo!>p@*Gs0<Idh7#%$T`s3SViA7@shN$NzmWIuvk*b$x;kvuhzBz{%7'
    'bIO_A955p8=R-IQoeW*j5<1;E8pHdSo_?kefiJ#nvZXve`N9waUVae)ZYCJPev&6Go@zAPE8!CPcpe)AZ@W~2PLZC~X=D^hKD8Y#'
    'dr0<)18zzY`{WapEZmSZ{v7;v-VM#*kJon|&s)V*Q?q)oTI_qEx$xdxNuYa7!lUMbyVh!IGw!d_`Fy7`7Vu5qJBNAeG-!{TK|_zI'
    'Dzo#ZUTnt<@fmBG8}MlM)i25=iKT<`$qH&$(e8xL;h<@}*48ziZE^LF1Q2mflDHt9+}3c~1}eLR6>Wf+iRFq+Op=@T#lG;cNBayo'
    'kO13?^s2s4>-z#?uWCQIqv6$-<X<h@4{ldeb}<IJH|?vah)FC97;X?6?wSX~kNfUXAgL)r$s^V%o=FODsOq)~r6|1rw5wM7QqYD|'
    'yavL4q0Mgx23{BTaN8U3?!{Repduo6MB`9!dNGlZ^<BJIdqyJ0TzI`-kC#3y!I=eq25fkFj{v<3Sq&M8IiG&GzI4erC&xqp#LjdP'
    'fNu5&<C!n<`q8+{Jf=Tym_91%LBP55<|O{@Q{i1{^l}S?Sw^*PLR=M6d!z((m#n9$Wj}mkZlyv4R`gSYPoRogUcPtCKg43{bBv8k'
    '<gJzc>7m^VUKt4hJZXjqU=I3Azyv~70+@lvB*0N|kHO2-vNK*Fk>C^NqN-wHl^Y@O+=FG(3qngJpk^!q!+VIOp<Cx3_5<lm+vW;@'
    '5TX(Y1!{ztz_a16qyo>su#~QhlX6WJ=}!B)qD2D}>q^HHt0_zPoR58p=cR?w9wG5(!XrijOfKa{Z0QZ!nT0}X=?9&a%}7W>(T;SE'
    '8nWD8ESRa4Sy-O+4J6}FDD_m8An1PnmVZ#>I+*nmgDq+u!Hnh7Gc8z|_+uz0F!0LHuPUIKpUdlg9pi?;GLE74%Y^SE?C{S!^kSqE'
    'C#{D6G}BY1%oMCU%99?*VC<dn@Oq--0{?=cg$EQ(sc~YQq7}8zC>wPAl|W^@hU6TD-Ch7r7>T)cl`Za$aheKH`#z6+dYg0IpkW^F'
    'lTAy+pn+fa&3^#~>MMXN8dPMI|B0{+u5+Zs^rkO`fHZ7Gm?TBC<$C6ioz@As-iHr*I`J(9Z0d?LXDpN2+q4PZi7BUmiS&4Z5*~-G'
    '6g_dEn&x?EaFqID@>AB4&VKG*3H<Vki8lBX%JQ34`b<xP%(oF$mLQEd93nwbFYjHH1i?%;4HFQYCTQ9-ubS)xOXp-(G3U<Qw4pKS'
    'z^clgB>9&ue9x%#4%X`>=@R^L`Ut!vsnV8q7wT#_j#CZu#csU!OKZa#UR&!e(A1>s=K^molym#UM&6w#HQ_NFA@Vi2QRHWE80E3I'
    'U#$GsocY(>`NJBHRMv1w4`mG}8RSVd#G1qti5jxDapLv!VTJYzi;MkuRiQjkbIyJ;glBxveczgjdep=_3P@hW!IcTpoQ5aGxtM3@'
    'qa|H!R{BIkai5p4LT9K-ey%CMMX&`C_#2&JK=iRo_l%7TMo>qXTJQ>NEls`m&*qd9%sGDA!@OR%KwN6d4)$@LmaB=OcsaXybck>G'
    'MwRHWlgW7F%$;TaT>4OGv8<g0=rsljP&D4}02POq7(#Uz`5FTn!<@uD8gNe75CoXOZ=fIvs=$lqtU$V`!iXxi9P|~O*|3}04|#Xj'
    '^@t>WR*$++4Q>k4h4ZEy>F_-9i5$m7JF~PVtQjC#H#^F%ijJs*>3tL)RTnV1y3(pIM1c-flZH!v5{hMWSX(d;uJfY*lv@BbuCYqm'
    '7wAk&m`&|pwe*8l;{uXm&#+b6H5{_r>eI(^ccpmtXC9~?!xN$$(^3&9TvEBi)e<w1J<XPEbmp<;_EMG;I$XlU5ynTJPi9Mjf?D!('
    'O(egSbE_qhP8Nx0KZoCWCGDReI~lA9Lb-5>e(EO{zAaA6h;IvLq;$9}tSZDqRi?kjxB)OF<Demo!dL20_nL?TgR|jKFG(;@Zgg2G'
    'cc*q$O6&I(Piu|Q-$Q+lWBL|0SIG)F;h(`Q{xN{Ria!!*ssr*HQrH@>#yg_XO|nX*ASHg179M)wTl(<;HrQbVe1WP}<mY!P>KTb>'
    'g@-h87ySNPcu10Zym*<RKTARyY|#WhY>Uk<sG#|TC*@&|Lpyl)gtsIDwg3HB+($!DvgodSRbuH@Se|2|BfFtKjWzV0UBHmr(1%{@'
    '*k544Hf{s<{8TKgDA?1C?TueiKbJk*{+BZ3arelFVu_+Q9t9)+I8O|O)i~IUGJCY-%>2P~r^2T-?9pB76Gi4KWmgZR1{m<kiMWEZ'
    'Cg{gmbKJ+-OdM1_=-P?<OK3ztJsI(L>(YbJWxzV|&Z~tu*Iv@uOiy@lo?A{9h|=~HR*HN&=Tn~_y+nEa5-)LnI<dx_&s5|s@Q`%>'
    '@|1I@@w_J3UcGr#ttXBffrD-Fs=t4qH6jXVH_2^l`K#N9YD35SH>}`cidsh~xySL{vivkaSPy=i48aU({Y^eZQ{DacrF1WthGVo#'
    'FTiXZqf;6TdXbO9uhfT%uNo_z6!XsN7{}P#dg9<6CplhqvnE%9&s-e?;}vX>;phB{B2RG7zF(R0Ys3jo7uToK>wKS&#iUwC@tlfg'
    '{C3cK?y7Kmixk(t{!T>>+|ZV_5}k4eDV#yWcpYQn&yq<v$Ds8pY+v!=GrJ$u^GiM;V;tw|CtC1vl;2ZL&a=EYG!~s#xtnheBQdFg'
    '1Ky}O9mBxn7hh|9*?26*xo6*)6q37*ejY8`g;Ufs3uXMI`6MCVL)9OH+!TQr&>#aXsf2z1rS-t(c4(LxjojrL1%XuFM0lA=*(7-V'
    'p5ygu782H56dx8=gT}<|!^y|>nxY>}#-*G!#lxI6!-Jen!SPM;+2O}q<W0pgCp49e^wwd*=g>D=2E-db35>{H1`SGlsj-(4*FR6>'
    'R)i2aZ$_h%b6A`lctWAz8l%W3O1bG7yr4Tc=jC5_RzPB&?<z`jsl7!CQaUK-6JbHK5RY43wp`Pw(`E){>@<M!SJBN*4fgxmT-h61'
    'A8ctr&!Um8r^-Y7OCm33H;HW@FVwX~56!C_@Z1A7eV;X;@wyrNsRZSnJd1lSVz64v)K2wEBcY}jhgNUL+p%=O^QV+z9Fw|46<$#h'
    '&J&ieYH?J_{@0-6I-*K>23N839&;Xhhy07e#jb-n1(m!cHOXE#sGDcRr14!N@6a+NMa?^_&0DYvXByRTfqr%kJXP8eobG5Y$7jtw'
    'FuGi?v_|C%AIaKmWrnGTOC4U^Jbyx}k5D0vNf*Lj3-;U|1m4UK9SD_zONDyk$1)T3R<nb!aSrQ3cF?G)Qmrsiz1|#mjCH$1V$S|M'
    '!)Zd#WyEL2%BE?c?vPgxMx`F6_Z-B8TU-!{xxiq~cZaJc!EgV&MW0q@rBZM902#?7Ycxst?+?*CZ_b`eSarVQf=Dc}EB)fA3iM5U'
    '@sIZGtuYNMx}?Qb{UxHG@$lHyHB^unlsyRjS>Im;DwYW3JMdb%4`Z*Uk}GX%5eiY`>M^UCv$W?(F3hqWVaIg--T-5l^jHTYm&)7%'
    '4*z14W~Czh>rc%`7eub-XZb%+9~vA<7n!5AwO9FHe*Q<)XJJZ10QCx~)On4w;#m`<pB6$ruyOV06`4PwEF+6%X+*XCHF`FFdb<m&'
    'dB$1o%AWZ3+RT4MW@@vwW{@0RIjPZ$&(8IKK8MQ*?N*w@_x-0hulSVvjT&0regf<xuKrz|G5Efz|HFHZC7Z)?YN|?a%bR*N`f)k+'
    '4p#5rp;Puvm3l9AXfoL@E}RH8lTUScxBX8RO)9<)v3R>1w6B!Zc=(L?hcmEcD-7DEJJVM6Pkyc)nmK`*7Bi(pJ1ld;*OyPcFodBW'
    'hJ)_Yvmo@0!*fT1-t!<DmwRpnJZk`Zife*(8<os>;$dJnCi#ruQ7LetBfjM$c=m$sE<>z(TNpMH<g4OO#&_r?TKMSi>$mJHxK~M?'
    'F9(<Li*~Xd;-}A8AP7H;6-1esFDa)qa_5im6oy)o4_ubMWRnV)Nu2Q~biSML!)hWZGZd|GnQ+3DivVts6<M3Ta6e>M0qDCFF3JAO'
    '%9iF$*!?%O*$2@&`<}#yX6^&$ZZ)Zqf~xn}0sC^#J-fY6>o)9b4-HPj1rr#s6@+xtjfjbC)1}L|Oa{H~Hq^#+@!OF@`E85Y)6^yp'
    '(?}5Ld#-3x1G>|1|E^lyhF+L9HR}Au?W)pmq2uNAiwLD%W2ey5_FePkuvTz&r`C7Nm(`ZmtvXyew+Mn7e6H*0jh{h-Yue*NBPG1G'
    'yDvN&J5OjkTTs6}8#kZDa+OOY42}!C!uQxmT$5}gYGUtcr9yHt!<lP8NaOJ8+k{?{7CGtd1CwERO1DD3edBiz24X!zBO{@CRw2n~'
    'Rg2cMtwlWb%g|d#4*O0izT7~qcqBY+20=PMv>360manTo+)ijrWN17#rg2tNe8*!WI@gb6Zzm4UM)hoGW7CEnkwiS)o?9HXxIW!5'
    'j;gyr5UnPJAT8<KuA5NhbxW`zRHjzLd3ROS!Ebi&O0`s5m7l*_eQ=u7?zBN_)tz^nsr_mx^Gnu0A)zoKp~<%=*$D2--BaFoZ<w-1'
    '<!;N3gNXX#4!NqTz`WhFyZ6iy8>q5|^BVD-)md3FpZhS3(4UcrhsTY6lw?wM(K+L;-x>uK3MS6TGaiTSI^q~xY|;!@J7B{`=&(k>'
    'W3hcF98<nv((HorFd>F_LD1M#tO}~$Pf%5;Uw)UWZcRkjW{s~NNSFcbr-OZIZMh1`2i(EyORIBeF)u+hsLO_4BJ$NdX~NK<bwv=>'
    'mF=RupUr}P!{I<_B^5c?u`;pz^?RyN?drQ35)(M8EZewm-C$1exXCBo6YP1Ux*)e&HmAqjDII0C3qdDDh0^t_ERJB^yIg*>aQ2a0'
    'e%PA_3&8BSrDcCG6B2x-b9*1Iku>*Q+h(}7jEtnV<!c%eW7=x`nSFPd3SK#Isk+8XJ6P0k5Vi+Zxjlxw@Y8h0+I?t1W8=!`J|4SQ'
    '!d?2g%Xr(70XHw~R<Y!#`&v3#S_Tg@HXxy!m6wwReZ0-Wen(*ec$^n?s}{2Y)j>%9o3C8kNE2YtFzh@TyLQ9LW*G~Xe5@h!x|`rD'
    'n}7|P;^ggE))<{<W9<ewSHmYX;*gen%f*{hVKla~F0Qf{%XY=72hgY)+RwnY^>K^Fp$DgNrK$|NV84l7U}K_spO6C)G{a+01H_#9'
    'GVX3Dj-v^mM+bi)Y)=A+<;$bm`$KDINuO5Uokp12B4!5r#4e{-8<;H(;J&f{2*U?8n>*45k`?wVjT1&B@Tb-fkG``_TOrEO{3l*o'
    'nJVuVA`#0G`GnWYyM{Ib&1LZ%t!U&*&98oE5$b+_7IYa6cBN**YpMf4qq`prK_&kIFFs!Sa%+=J)^Rn>k`Q}~18#1IH?y)~<|$s?'
    'vwENjonjQ2YAo+F)#G4dBJ5dPBSWR{RayLTI5@M<HF&mMzhpk#H5nPAiPJ2x?S$#j?h#yiwEcrGjV9I9=3kb@?l3{>FBIP$PW!sK'
    '4p%S)k`W_lUr+@59X2qoKrHLIYpf6)nzjoOP!1hD?2M03N<KBerv@uaM}u~Nu;4fWPO%*U)?$9&$*FiWk~am9MnjDcnKI7d^(R%%'
    'Ta|3%^GAYSO_z)F%W#g!`x52kd?C)9mWF;lPu9zM%|*Pte97Hl_pq5fc?jibyF<ld5mTZL3|5+nOvTMgeV&2>n-qx^k6v6$;tDnW'
    'crW|-pnbs$U}7o;#9bdIBoRaTL3VcFM_1xyGX@~NSXBa^qk#mZD9&h>DDIg^O*SPBj|WIgaw_VA6Q)-`a>)O_qL_V(TzU|PK&Je-'
    '-xbBNr6LE7GE&}eG`;!}pTqYDh;oi!kWL>|mcp4R^N7ze>1YyseT}eG8txE0-_#pteJ*-1`$;XPb_R?KM2j^f`r@KoB;2fYM5h+('
    'dk;O!ev0EBC)^_VXa-<P%$b9i+$&E{!>t<QUgI7^=|N$v>i;ox#K$M~=T{XFz2_E<v9EBqVedQWR}Ea5kNIUH-KXh*se@U$5e+|1'
    'uZi?5*qGJ8C14eCajzzKii4)+)d*=sLibY|QhT)z)RJ1RTXq*kCp}@8PXSd8#I1^Ut@y5_y`qIj;Ztp{{I+s5XU<iofwZN{m)8Ho'
    'T(hy1_nA#4`Fi+18bUQ(Aq14-Rd6w#_g4+hD4>?wNvNZiS0aPWaX)P8EI_#T!5~T|fs4_94M<?cVnR0(2*D)Y5jgEN$%kWMX-={2'
    '_~g>|P|fRV2Z+eIuLkXH>AqR?Q~}5?<<}Gd)XEQ$09cAH5}*=WDgn^=lPydV_Gor=Mt%Kt?{Gi%0?0E5waZCHW~G5bX>Bu1u)2Sv'
    '|5OqDp(Tb65k}pe@Mz_dATjpl!`}Q_pceVc0902+dq+^;QX}|ZKUtI8rfktw(M0K4qWw!Q^Srr#q0YC1{i`w0rX@eE&mv`gjw$OC'
    'qO8whWqsy?tEdkN6Dq5&AG-TMTCX?FC{RSfXmvkx1<%S8x2Gwd?8G~VFtC_0B-b-4$5hOK-28gdJq}_GkpSZli5k+)8|c-k##=SZ'
    '<YY{NDM9-$*h0->BQWrQ?i@<Q2r3qohV&JN4U$}-H7T*AY%ODsQdM>AR2nv~WbI@8+=5#|)N!v*1&2<?5KhR-0PrxCavqUc849D<'
    'U*_f37v`@o3nS9eUah*%<pvOkH2gcQgkJ%-1h9g&OqB@VPGZH_22ejiq(x@)<XJ>7_5y#~js1+f%AS8Bp`fn~Z<a6z-~j!gTImhY'
    'I3_K^)EPKI6146234*Sb{YtS*!Cr+ABeZ#=D#G);mq^v<)CKT_noE{w0V?tA{5T5Q<92B2!rpy{V0U_|%3?ySD(UYuPjA5P0s6x4'
    'Ws`LS^b%{kgD}55#1#vRR-OD{E?TlWJ3}PU^eqvc4%hKq&Av%n)uDFLEm>!0Dc+M+sNnR=WtVnSnx#vjpbWzkvxO{opv`Ep|7Sl('
    'ki`_$foZ9$p~g9k={)%@`k7V=xMl%M*w6HMV*uTZPgQCPo@W(q-z5~323fh`3VS-XMHSXRlAi1fF#b9Q_M}H9`FWnge7V6ozF913'
    ')hS99DxfoB$7G_%am?4r<AoyzQAZN%bWL?rKh-8CVAxblc0b_%teYujO*f?>`ulI@bak=bd5j14IOgrk2red^*_4IM`PUR1GRH9X'
    '+}LkA`*uzI{a4%v>Is6%54zY}sH<wS&69yYoT3++ItgY_zl4;5@@K)6nZeMXxK<hqMlQj)RR#^V>X-C>DftHNxPL-jEY!8F5PJR`'
    'cH4yJ*4S+uR;RRa;uTM{-z2F%dnvOiQg-ZU@>p>)I7gGSZCH!5omi2x@O#i8?Cg<fViT7=+IJp$;&hk~n}rR|M&6PIdQ0UkdwOv{'
    'GYmBnv!tarDGR4;<-=XCv!D&m=94x=gDG1gWj)YZ-076)@u1*ul|5%4PJ&_B<ltLkas1r($sB|}b_nka2lDMnp)|+`CtRxt8AogA'
    '81YikT1;37#teOzjK*87CByr+I>$m|KeU>MjfP>r#n@;hb}xHB;>J!{?IcFF-AfVQOsIWj>eR~*-HAYM4zh^!J9*r6x)e0ZT$yc`'
    'vWVj!ZN<swDI%lVf16Fl$m%Z&+UT7f02PwvC>EJ^h^t?JXW><PdgovxLN;j%A1{lmETq}~ELn^7wClQj&?*;`Fbck}-skM_@d}jH'
    '^;4lE&&T$B^2yaaQ@+-u)RW!CwO*8tn2VdB;V-@mF+z7ThMmaSzUghGnmIbjl3&x%XwFZFP2*nt5k&7^D<!x2aa=taL;tX$U~~AD'
    '%`}R7^v0g6uxT?~Md@F-vM2WFk3C>>M5F_en9vhRqlmiMKuDGbXFJfGGbgOVS?F_lCyYFNw+-DgUs@*<J~taM*i<<~NY-8Qz%xFd'
    'h~*pzD}edfk+X%^ma|ScjWgK#!sUS!=1~#tF-&Cbo)>o>P<&)|rXdt0u5_m~3`kZk5UOmE4k&(3XtZ9??%S~Eq^t*(`@$OJ){n50'
    '6{sZlTXkZmpBlKkgEb~B<pHYv>T?jcLs`4*(Yj$)97(9wy!-pNSv%?w$~2?jZ%;|98;)yX)ddS;cGtCp>*<>Qguie%O+t;g9~en&'
    '*vCkd?XSzm4!0maz;`H+43u!SeBniN8V{>V_c)__6Ao?{rk5kMBvFH4w;czoyIt+Y7zoZ?ynyiUC)SPWJ?F)4&vvP|<lD|d2=4Gi'
    '57>LKI*lafY7q88&xfP$xRK1Kk@11)$qr%PIfv+e2l)xY*xo03{{wrU)93>O;cRJRj=#Z}^#nH8kTobh3$|)rcxo51h*}p;*MtE)'
    '<HxdB(s-;6nm$idiI}r?az4>W>4HdlGYV1*I#bgm41W9H<0e}QE-2OHReWP!q$2v(v~aQ<)Prv~f#Lj2aX};tKdC{FTmO(`_%Nmq'
    '#2UpK)jspc?k9+M<?a19>vp6eHP2!+jsX>UT`>X&#N6c>X(?O+MmdNW1*`fGXts#87apo^CzeD1Dd280WHRhEQT6ay@eAA@PE<7F'
    ';<x7nQTT=|`~d~vNT(ci@$i8ELO1>l@%u(lXKS?Ls2>A!g#oEW5nFm3@1=ayA7S^U8LbSjRR1;BtoPPqBuR72JDz><IY9G&z&AQw'
    '^;u8UE}`3<&&}}Xv(HeX%Kvf(RGk0G)o(sVyPLwfA)r=5Jbc9CAA93mj8%gbSOL1kg89CmFbEyoWXr}?d8IplA56&U78+fqak|}#'
    'cg=sTBCq{+)7*>}y5Tq4WX^^ytF@lj9<o|xXZPPI)@vuEbz6aWwDzO4Zr@ypB4H!sGQjB=NwpPrg^<r}0F#sFPkY1Z1QpnzTg<j3'
    'doae;lyL7V;RqQ=usn-!hdS(ds{{K$$Nl2*qy0tWHTkWY|NnURC&;3XctG<#jCgnN9smwf;3L@`JCNO@SrhCqj~Me^)A}8!iPE{A'
    '!|&?X*iA;f<b-Lp_rs3oXJf9nhtozY`vXJ*q1|0+e(8Sg>mQ&a7{0KISevmW#!$=qw$C=0b;eeA7R*ULL1#?g;dLVWRl@Sq)b+u('
    'S!wM(nzj``=*|m{_8qGD6^uG@k*1_8^E$T&I&FiF!j0&*<<6}dp#nFIK6SCaU4LcO8hD$A`3tT@e%55^;WnwlvS|t|^=q5V(&1?t'
    'REan?o2qlxJyz%j2b8KsZj(YdjeIXQ(lC0B^NeE?YUw=Q8uhwX@M`FTb@iiC-qj^}?r+e4ol7kF(kN%&<#8|mu7I^5OASu`+tq4$'
    'YjE&}D#h(dp4Eg^`GiXIS@6;XQ#!}j_@0Fw>3J_mEZsrPHKtS_`V!9QNBCzf!A_B2NY@t8J^JOY_cVja56*0Q23pP~&pW~7d#4<p'
    'i}N*p*h!u2mFeKfyRRZQD9^P2jEZNaR;!)XOZR!1jqPAtR@P^ui~i}=24t{r*I6QXWqAF60?P}>iKb{XLqC`afH%kS72=QGxf|wC'
    '56%7k2+L}1$s*(@TZ>whu0zfFs7+_;VIBV?0PBMyNaQp)Nfcdgf0l^4p7@K@U}MhH70~{y`%Mez+!iif6>JM5HT6{XM_PDGk7Ifh'
    'Ms9GYTkF=cO(N(=k07rHU7>GNc)$zh)!uCeXmRzam~_4=%)zg~@{Zczn<`tdfB!936Y0F<NHY%aDgDd-*)CA=*G}983#OR7KA`bH'
    'Y+%n762agpwGf*{TG&}wQ~?Vi_SHG)@<4cwd1grVD|+h<z&jCUdG5JM<y%JX+zV9-`ok(}9~N%+6uZ8f1G@^rp-}f9)SQhq>S2o&'
    '*&47UJZiY)-`8;BWQ+DOpe}={OT|oOU%KAH?lF}2#%`3uvBnRw;?yAM$nB9}g%#XVp;J-wz);YLIQOO}EX-H6O;>YIrAwyEKgw6;'
    'su`a3zCH>JPaU~p4(sw%k6(aeuVGV>s>4V1Ral|ImC$R*^k(OK*?2REb%o(ae2(dX%A*ya@>udGRY{QGug@8!{R47O8W-Ca!QbnI'
    'PStqDVyNfr-U0@u3Q4`8i@V6ntzM$g)AI&Owu*JaX!?A^eGG6C+I=%e&rV_?AZ9&Ob2!uu1~`9Nx9xIlPyFA|t%(>FvgYs45)LoD'
    'LK9Op;42r#45qYw--!vLV&%4FhbM7X>H!>usn&B-aF9YYZ(O6Btgf-*NKxDIp1lIVee8&0orRmH?5T++o8#a>+u=UFOI0r)sInbQ'
    'UR8hN6LVt*(X@>_i9fC&mVjm-ciy^2;3AEzbRig9UP2Lb^<Y!sGpX$dkKYp)GIBbJ7&MrUy1E`hZ_uZyC3~Ku=@e8A%wurF_?)+U'
    '<Ih$ANQxykVh-nWyAQ-rCcSlwJyS!RS4oN&Ib1H1aV~#-9meIPJD(8_YbxquDYl%)4LA2Q0GFN_P`5x^5lTY`rYh{?=i>y06DMy8'
    'YN{c>o=60JjR}<5cYXJ+Q##|b-umA4twf_e7Rsl_%Q>ftw-dQF6~g&+Dunap*oJf2m3#7WS?Rlu9${iG7sG(w$93Q3p`yCYx^q^U'
    '2v1VF`}v{b9n4!xuL3eDa~?-OaPv9NzdI1uRGge7vR3@^Z(Xlgh#z#SqxhXN8=8|MdQxv^<X+FvCW;sDWeM%Yo2zNU9A!vfYpS-o'
    'BSu#0$S-e>TR;{;Z_fbeZojh2E3hloJ7uWRJ`AcWiWd^s7vQa{>*;ULd=HGvNf~0amww*kap^1wEQTL_#WfQjJW-C-`BUM?=@_um'
    '7+qQ)7W-bA2cljuJZYwQRGGk9;{A;zf4ZbcvG2tWY)S8y;(3|WG#<hSiU9o=d3Cv76QO;{9gFcfsk6Q`-Y>H9Qnr6w&YK-h2ZP4v'
    'u;R@y4;|HM`0XVr=n+dQ{sB2U5WHQ0{c&;|yDb7#Nx9~3CV|9Ip8^F~3x^1B+{0mTRIT+@Ds1fgx5hBy;aG^u_vKr_-v;}OTz)m#'
    'z+e38qr1pq9-H1%F1wTnV;+tmA@3edLyyCIt`L(gzjaYg($@&+B4m`8F)%}@;i7YBxH51(8~)~~Z}92{$gYc<iQ-rC4RF3}#qFE1'
    'KaN;~Bn~dtg0s;$j<eOoMI~kUJYOcRiROuu#$B2icYpr;eCQ}W|F-h^L|M!3_i=r@KpLM56=70Aw&SC>7S+h@+>!Fq1GNi06;FP5'
    'NdWS`$oMoV<0u}KNtdp?Q{3FN#8=dB2)LkwDmZ#LU#-!ZWYFpL1{TfG<lP(b{Xe|ld=gHmt^w-d`>ct}@LbY6+GV$gc7&TR-f+Fu'
    '&;fYU*2xWJB9{qE7+Zx!%n$P#&dA#2A-PGGFzR7{NaHmg>aL&V3B2NW7{H~l4%FXD_3?ZW;%*3bc%u?jyE9uQ>4gkbPI7RV&d_59'
    '$A<9)SC&3PbIa|Oe9VG+OMzihCBwFDn?+E!n_^9^)!oIilmr^6B(z_aQ&ZH1TOai*d9h2{vc~Z^Z5)vT)%VwSG=6){oxKV@OM?j0'
    'i6!iTI1L&|0c14a64|~^$mj1kv{&~Et`8QayVXxH%J(St6$auJb0r5p{RAn%iEFbLkJP9k=92Ke0LH!S4+C;DCrr#Poex8jhtvDa'
    'fL?6#oAq4vw2?46+a=g;gUkZSpFdU+#$S=oNy)KM0rU9XJMQ7QDnp@sHWv>EgwowYESt!#71k0<QdE$hZb}MOZ?`qZ>~J}DtSP=~'
    '#5*Yc{QI(zn&2+Hc`0HDqYWM5zHowDWilgAV_^syth3-FHK_g1zv4P{6lxMzU#f(zXAi<=QwOO~0f8hB)ve=3EScjESk^Mk3PdmI'
    '@{w54RzHs{p?+%fYr*1&#X*aNJx}k!o*X!L5Bj}7a3!s}lMs1ED$=GRbqu*tmCk5?+RW$Qc~Pogyr9kXgJ*p-H9W8GnLQt?$OgIQ'
    'vxf&#3ut=9`&tSais!MZNGsudwL=lxaQ=9#MQ7|#lhSDd);@i0J03R-I&{0*(js}%T9=|7JBHbm8q;t%eeXbfn0MoV&ZqfRYZF%A'
    'fT8W{iVc{h?^HY@mLl5e)xYVR7zuVoa=#Z)|F!qMY0&frYcBeiV#$58VXobJrw$z->T=LU-CE!h3q?9Yr2DU>HKsESa6YA`Xd|Vw'
    '(V;&c)7@%fmeN)bzmXQo{{<Z4u@eWQS$;)n1#z4CSC8+KbkHz4b`Q#3e$X4FCo3NPRaWu&V9G}AZ^cJ9N~d!+;b3M3n2FolVTiU3'
    'TDJe!|1#V<8}~)Onj8N1FDj!MPOC2JZH`vPxa>1P?=TDxcE^*m(d8E}sdMsh%s`lphCAO7eUaOt&MY(_SSR4n4NE$+@BH;Dme@(B'
    '$bnMG@D}iLOFVQs(7=)d*MGH(f~p><d0%$QS_TuaAyonFQJ1r+Sc^05)6uq)VR;!Tn~tYtLvh6kPhE`YK0}vLp-6^eNLA?K@3a{_'
    'LK-%KcB$wIebuJq!+MtkgjhnSf(?dtRt|;QXaySA9uD4&t!LxVq1d{$G983HD6RD3o&#<U!+r)g+c&}`x(7%=OI_HWt#E~dK_vA?'
    'U<tp;;(g6<u;~jOyQ&a--mP?nJ5{mN<ItzEyo^=7Mus*a$OA(zm4lPXhlo+CT*Q;raTE3ir#%(lCN=fM85Qr<uTr$Zn8wJ_jOESv'
    '8DjP5<~X+DU_+7vKCDyOy6q;mY+W{sQ1teqI$&1l0%JYV#mxa4Jlg<EN%~%y1cs;2!kAP-R2v_QW3YM4_RO0ay8ipG&qHgHg>O@D'
    '5M7^`RTnDV^8~x+((%q1==*RYjE_EP+Hvb8l{S&lKQIH5JBPS=67ST4<gHm8JP|q|5B>pnf_SPdoWy+c#X-&f(p)OG-l^z)V1!kB'
    '@Th#qb<_`IrYN-}Uw?)b2;-!lE`NrT0A{8Tf39-A+MnJ3bDX60fJCMFc^oWe!Rwl!7NXGq{~Y<a-7>5ksHb3lM~X?S{0bb<_ss|='
    'YVx{|HYuw1>v;zHW~M|F#(Qp4?5zdA9<K&0>P0U2w)v!!(&tyZCslXXggcGE1bc$|z5W00n#WZCO?LqnZHI>2HUItl!Sl+ym8l;u'
    '5A6)r4^4|lL)-WLublqr<C?u65)uTu5t}FG0tEH!a|%XTRd6l)b3NFrJLT;W$25L*xBO=<aKajB{Jt$Le5RrP)E1g#wga2z8Zabg'
    'XK1@Jg$tponJXS&#2yO01<pA`uy*l0VOSgpwFg7_v-{8W9Lz1V;m1#ve>p!MJ18R;C1R8UT%d^jPXi#Gzz2davJ=WcUJ`v&2d<ky'
    'h!zloD4FP<t2%Up&8)U_Mh~n$wDZ3Mx^(E-x-VE)m{!>;!j{-%Td;@O;kFm8YEG&$4SKih#(E>-o{bKiJKS{6Osndh2HfSf#9>e3'
    'NNTg1=WYd7EuClio%b;n_qE!8s4CR70=JsIY-Ahd;99fyqA4^vTJHDhINN0tt2;KDAA}1u{TrHbUWEpltHTl)=IK3KESNW|An@HB'
    '4`I%#wK@2pd~<k}6-(rMeb=>w%{Bn;Pc*>vjKfOnZI|0`8a%hnurCp<3|Gr!rwyUUPJmS;1#KbzdlePigGQ3<6tQ`RD`g{yj2)~E'
    'UG_qSc+gMewDVr@tTUnw$l(ac#&1|^KUQY{&R#Zt{nCwN#kp^6;l<H>V`bXO_MD@wvGPop&-Tat0zu{rV>`gI2!%&$Gv4rM1vKvs'
    'OVlWD(jOLUz)B)WJM4F<3|a~H0~|>LblBSm`nov`g%O)9SHs4Es?O_otAfEfL(uX_W9B&eUx~KW>wnC<dTcnLI>G=B^YXx%rmV!K'
    'f#XyjwCre%ufG`)G2(CU4M(+xmIa@#AgdT&5t{9CX6|%?9d+E~brW~3^PzVzenf4x`We8K8VS(c5)vRNFfi9eX_A~kj6_6)i3Rh;'
    'A~D;v;Upuz5e`$-VB(to2iAF&g?T&u+BQA~ru~*M9@*@=I-t$6iO}UxTPNtT7uMMwsxvY=;*#eGJs2dm8fMKU8<aS!0@P!v%ZXmi'
    '&~NQA!wIWl&G?oFwY*yx`8o!a-8d9RuHQNYMr^I=x7NRgnXjFTs`EhD)PHXe7_+Y7@zrjuL7u&Ql8i>uu+2^jpj`M@t{WG>Ijnz='
    '#gp#B8LQqJW2pJha5;4J6-u7kD~F4<jrz963XQ8ReSQE-pTFk`By2R_N^BEYD_9qd7R=Uxzvq96#xi}~4k1RpCaI^(RpMON(@S>$'
    '?C&vK#Dc44zh<rT0Dy)&*(z>h8#tm-dExnXdOKP!hBdHHA6%z*tGx{TpsMwp4*ka&9fO(Le=lkjIrrXV6Oj3{GOP^Y1bqj`74t{&'
    'P_2|FJ;7>)L;{wUf6k|?4~O&2O)RjrJ<K*f?AY~I9jpV&Lx+?ddVMk-H=LuHl4uN*4sxb@kYwpZ$Bl=^iIZxn6-D;exOe8Zb>74i'
    'cJj2_9s*SpXaY=@E!rxHYm!D#aa84@E<mp;(AHz!mS7`#!j@ChMPXXeBRGSR0U~RELu5lva3%{F(mie4+P$-Zez5ki1)r;IMyXa^'
    'u8(s+E<vlFC<iQiXFA$$vit5%Hlj~-v|Rv7n0u~s<}&WFPF{A7#|^4IqFQ$>yHJwOw=Ml#>%Z<gR87zod#bnhSZ5bduTSP|=#f58'
    'l#yWaIdinN%`o})WN*5&d-}XiNvj~%{Of-{Gb+C)0Na=-zwcp+dMvo^>IwXWmXRH~nwlG!d?r@fE>`3cx4stZK#7(5KH)({k8wH*'
    '&^vRnOe5Y|yHDm)bx^$APts}BJZqg7^m)fF;cF7x!GQ+=Y5|0A?E^c)h|vrT@`iN{8Bj~?+)n_o<*J;3-r>#a%~o5V*sf2?ZYbxy'
    '7B<~%3uEhoee*l&oWZu$BGXB*=L~uk)TN&Q9I6Wg_pf!D4|Q(S#5y=)DU+rC$G3AG+Fo12a`6Cv^Ei@sy@o&^_q99cQ4?%AxR|Rf'
    'dtH`Nd9nc{Zt<G)%?owTT*}s>QqhXChr`lMqHvH(kA@}U_%xW`qU#>SA@_B+JG)MrZ$}jNw#L`jsnCeo6j((Ry>1C-MuA;;(A=IQ'
    'p4aA<TwFUnnV!2utx<9})g9}In02EfT0@;TQyA-ayYNoz(AzNqdKrOQG_(z{ckcm5HU?eZ6gB~@?b$lmTCke`N*kOAYXL*@M?hIm'
    'dzlyzBOAiM^7k}x$I!69PBWUf>u4UZZTn#2J_{{Dw#`ioE)vtehN?3BC}=RIQF~c_l$iW>OC*P;DoKi1dk4Ag_Q!|?$G%bZD-!EI'
    'q8sRw*m9{c96t;rXqs5BsWJVj5$nKBZvCTcKYx)hjB<b)nPM2uZY~U}q4Bi~<yze6$h*l@nj=EK%)LHSa%RktSnl<mUvrNQ>j^7~'
    '0uH@a9eNh7Q<+gTAM^s2!<N0E;Ygy(%NBE4pFbpC!Wqvc);GaK@=RT>4Xypw*%#KUS{|0LyF}HOT;?g}c`PHTU38w&n~qrY$acNk'
    'vQBp$JK4kc|92f%kZ_{GbeE_v(_o^+uwvwCS7`eE|HxCWpv{(sW2aC(7O2mGcI{xHIuUF0k^lCNV`^Zl-HgU?yC1|dtaQ-J8Z>lF'
    'LWs0DhJjmi<1iR=dd4HueZ0gnlo#xV`rDnZICLdUT|-G97fR+VXz#n$N8iB9{<O;CSx{5v$_%BTriRD1*btF1InQk18p|@iwjq}P'
    'Oa)s@_s*2qji;na@VdjBjlCS!!P3zXqp{oD)>h{qwv#nE>o}TNm2LeY8q~X{+8P3@Iu+kmsbV)^o%$7z*d<mOy$n2BRJ>s4r`edR'
    'SoJ}4{L0xaKs&sP+sZxdY}v)QHFE{6&#t^xv9&8~>`#fUrAQV>RSDWm?39U!z1uSuRF(h3liCrFOWl1z5%cKbm*<P`ZBT(I=(1}%'
    'Sn*nqnIbvX$1I?K6EJ%m-5JczREt#~f7c-J!0@k1R+ispVX*yet3Btz!W|s?L!27rww4gBsmvEf*AI4W{Hn)-fYtF8sJdHwQ)1sw'
    'BnzUdonLQsaGh_NrITR#GS^<v+hyrwn6bpjbKN1MWkGhQj5}?C=}Rf;?M%t+`JFDWJ*?k}^<AqYB>7K8qs-y8L6*y>D7$1GcZq4x'
    '+M`m3Q40sJUwq2BV{2EL0X-G?yZBm7=<4Ct&|#chv+~g^W|d&<%0-Tcn^Rj=SPmO6_v&X4^xt<qRE_DkVN-?6oqBD89a7SLJ0%t3'
    'R-RbpAFMn0WVIVGsy3XmSWbNJ`N148T@5@#47sNaDqn<c?W)nqFjHsuiG)I?o+*Eg4PgxZU}0Z?(HS*P^oGsb1_G4Ls6->b=P9sT'
    'X8dIB*6S4}cp5yEO)v%T4#b0ZK0)l7?3Na&s?eC+vZ(?w78_0mgTBg*`oz2w+N}_;U7@U7=-P8-XqwUp(&Es>ydykxr(vTTz_AyE'
    'Ynt|Tp?X{no&NRFb?2o+RiTa-$wl^;S<7Vlp)jYVg50*ydv0C?i*;ASUz@+PMB1_aU{}KjpgTf^e{K=AzBW-orlu@nTRx76u&=RY'
    'bB)E?+6!uL-(3CQcBx;y#?_*j+0}Ra-J}Nap^4UD&hPH~@yte^*&dyV{oKP^jRiC^w6`d1Y<@nUeWppz`+lO?t!k;Q*5)4to%`u{'
    '2X7<A_T@hvSegRGeJ6uUCx3M1tIzOG;0dz(HNQC-*%~HyH{9@z@sOT_mZN-DtMOf7l*fQ$KQ?*@ZW#sM;60>Ezuw<pYxDjnw9EW%'
    'ulMtnVfJjOe2!?6`_?Vy4`ndLCBe2O3}>w3m`IR5N$*p^(#OH|-#q=7&;Ps!dkO#zdwSY#X~@wChKZw3>U3zm<i}64(xJ&^Lx0vG'
    'w&xqdk_zKs`7vMThOOGq(1+0#1!qcZjOoGCZm^>3*ikSpgydV<tSlDFCta&O9>%&>wQ&zwDcv{9)lUsp$-!6dSfd9?TBBVK>nK8#'
    'TS-cd%9DodJxq+_ausi_b#>tH_AuOyj+bsf%_|i#vVV99V$YI2#8wzN$M>%Hto;T{lRK6>VRt_;%Nzi;1J>FNe>Q$cBWvxiUZd7n'
    '6)*YlIk34mxON7|J}_h+$US6GYs^@4kRR5B`6Hl@BXn`)bp8n05v{Scz(~{40D3tc+AHg|gA#H0uaB_%rZ(zf8)7?HKs4Kw4uX!V'
    '+osoA<iAK^MX(wwjDYcFU_PkLgl-Kf=YQ?pPD5bw2nd7Se?eeb@A`18hI4Z`TXxb&>K$!Y=OF-W^IpzR#NqvSVl?OZM6lewcLa<9'
    'Ro)Xrla(`rXg-#4kb%xx65O@~`TIkESGVaf8ss+#Q?=etRdyGZ4>2Yt;X;`iTet8S=t&)?>$HQoxHdbWZ5xXn5a4m<K^sC=tgoh|'
    '*IEB%(2Kbtku<Q~DI)#`(a3;M!_iKgiPhcc=nY*rQHQVR-f~&L_ON{8-{9GJpf&iIt8Ta34l|DX$JZuyj90wO*g)VP>QHrN5=Z`}'
    '5WuS(+OiDhje_gYd3E{YVB))LJ~;gar^~qf1!pTX_T01;8hSYmg#(SK>AY(}kZ!BPi(}a!AX<GSlnI3i>pdDlov%VK)p7aeur*DS'
    '9bhSfKMWfREmzcsKEgDl<qDy19X>>wSu_s^e+P+A&k2k$%>EJKpyo~xP|pd<h!<9Cy{Oe%?FNlCGhj6pHA6`Qm?`bFVa<lcGU&%h'
    'v(FTD7wEe50Br9)u*#4+OJJ)_jd|4u_6OS)rcP?>YIm$*Ibi;-!1?t-L&WhQ(WKfgyCw5@LX4I87OM!JJv!qTae0F(oAa9DT3g#^'
    'hM+=&Z~Hh{u}7}vexrW>3|p67LUWQ}NNK$bGI(q2>|(%Y=KsU#BAfp2?A9MPfRQfthx;}RBvy9RYT<tGBJ5n(2)IEIv;Ht-kDb@Z'
    '{u%3>4^<F_jyx@CWm42dcDu6364f|seG+=7+S%<h0jh-kc5!1vPFZRG*47)8FyE`zKizg+xZ+N6V*;4-ZKptjxZGaptfCq1vd(2F'
    'G(JleY7bIP6;%~=U4OG&L#nKW5B0H&t=k;vpZ>RwS5P@FVeCp!W^Zk6PkcF&GP+Zn?(Cl4Q#9C@e?DV(vx+G6^Vf@Tz8yI2HRa!d'
    'uMOYWhAWs*OX#DM+{0PV@eGbwi<d0_vL@Zx6UN-A(?5N{7Z>{<rvG1iR~{DCk?nuoG)uFJqO1b4i@0JG1p*o{U|2Nr5La-CVn9Vv'
    '!HCdwL!;2FB8v#Jg9wOgl(<XApdv1~fSNHRCV7~=jFU|M$b0$nPE|Lq;QT$`2i!jAcJ-~gb?a80t?HawN|#DxClL4t5lx3b1937J'
    '*!-Bt<aIT*O>{wgw$De73{NlH#4^O=Rv6*H<0kRq+0Oz4|M@ZI9y3RJyE-FL@i7}XQvaI)LkLRe2qz>g2PTqs7L}b`Y=-H?h@Fo@'
    '#?*+1q9Qig++mW;#_J=|lzMtE^gcexk?u32S0!t*qdNxY5(vpaUrLi@zlDyyDkfgNQf3Qe%U>zeG?{&SES^HYjXO<cW@jp;*D>EJ'
    '?N!muqXU0RE{$Qu3BD#MnAS>fE&1s%mQoVJp#5#3-?IQ5%+x7Nsu&%*21fdB-E6)5;`?9HxDggdcmm6p%&nG|Xf>qXD=7(Eh(;G7'
    '<!$7w^DXFpCsmB_-f8eVIeOSvJg&#<NRI`6B&vB=1E#Bipz<WS7UG^vgzFcMxN88j2tX2nNO}gFQ{byN&QIr#YillZtDXTfH`E<r'
    'N~O!WDHBOt$fSV_+!i_hWNJ$7yw`JM)W)SWxc%g@!!I(6v}Ugdj&ajmmH<mhW1iZRj!NpZAD-9Y=DefF`5eOhubED*ktSz}o6U84'
    'tg!Tiw${<})|-Fxz=xlk;7BM|kc{c{K$nXG#TR%8{mIG@r!IVDn^x*wYO{cX<YToMttPzAS|yxm+2Z?*(0<0W@sSU7Xyi#QOVUpv'
    '<npqRrFiqWylf-qbj0$A@v*aI!(kk@tStl)Zyqesg)KT<Og%!hbfz-`Ed=XWo@mj4itb!*QtFlu5T(XB|Ad{cXw~At11(EyM@1}+'
    '+Lx7A&1|cy8C_qUmnp;Q5S-N`aL}5-1ug&Lto1OdOx-5^5JnZm1EeI@nKmT*5gq3nnS2h5TFEuYXW<lTtO;bzB;a&p(+$VbrDZc@'
    'Zq}t`dn5}}z3F`)A$B6G5gbR*qe#&yC=c&$7SZ2P-Jv0`1<?y|5e{c^*1>x*qp9u3zp_jmhK+LqvJ*4Z6>J$m0Gp}_D3TW-AO>GB'
    'a7qcJ2OWCs9r${YMdh&QKh|8cgqdnZbx;daYhL*rCQ+dR?!~@{XEq);C9r52>6Wri8*W$H#c)fD*ntg4NBsESn*FeN{aDj(DJjW4'
    'vhK<lzZjgwhWUQ1B9S2~Bx#(|Gqp~UT#&JcRq@O#l}$eA++%A|nz02b@8gVig%dTn%nN6=Ey_qyO0CG0AY?Vp>Jm6;P2jvZq$zVV'
    '3nosIORaL>7coZHO4^a;&6<7;YkGGAjz>3MRK6H`-#s?cz54@VH0YjmNSkzn3$n4tT>#tDWdZ|K*u-a6s@sNOPqRbBQqU2;6t1US'
    '@*<{P!O{q-F$ar3A>epv<()Cd_X-cqblnf)pchTTNMT{zcO(f;2lr8Z8YfQ76&_(+z191~xP>%wQ@qd8K=p_c93+N($FbQE4at<?'
    'd5#3)C|L+{7I^hK7dMF;CtEjz#=#k5>WCXks8AEO&8jI;!qg-ZDdMG_3)M%p39;7?4xhuk=3q)X49?DC`~@B~(qk6DwAG&E5hB?$'
    'X?PF6FgwKh&3}_7>b$N*PFzTEGdQLJVRHb+Qq3o2!Q{w1e4Or&*cdEJpY(Fbs8z{p;CzsTL_@a5+~YD6+c~Xa{cuTJW25~fc@ljI'
    'F?QW89l+1xl}XndM49c@4muJcx@v`aZiD{*)-Y_p>Ib7{4NR#Z`KQSn&PvnPfaC7WWcR=UhK8VE_Don<7OSF|4%$_b?WOYR8MJS3'
    'UDI!1?Q<~YbCZRE47xX8PwW&!rfVMaTAK0J@!{Kzvjvfxv**59NI>S6C_$ES+zRJyZ-x5u|7YafU)QN-tIzY-abAFQMcqXAdJLaa'
    'aY>?$HEh%uw9}dOIfz2BDX+rw4Y~Hkgm-Fx5ERwKuc%uU1oIP8Ct1z3zNM2+5^K&8qidleDt&<bX{5M20dZ!^+~xlGpvm>3W3F+H'
    '_Ev#(z@{-sB1s&x19fHCczI7l^H?YZOQy2r#0f^&*rDi9jMYhDmrPqM;^u>BYGhIFg?t%8)1tMau;juvO3^<3XF6L{o_LbEH%E)R'
    'Eo14*4$YMfttG*#T;r-rX|Qe_OD|cg12!c1WY5yNj$G0?U269)T&CLLb)<Agc_kAb()FvxnGt>Q3r5v=^Ape^b!SFZg)b&FrX1!v'
    'W?nd&xf}Jy3WIjed+mO2H+8(5DRR6vt}6*`T9Bq=<n5wD8oDIsj{X-tg1DkEQQ_88V6$Uu_@ddKuLb|JhujAiq^7N)96Qs1gk3;H'
    'F{#;1yW36OP7vc5%x239NX1~2B49DWSP*!&Cn24)wEgZ_?8S_mB~}6iSEc!#B(n75S#tze$mgD<^nKO?hXd2&rf!#re(0q*@VR1n'
    'e~Mjj|8?&_6berZgXdvqSC?CVq77q|X#$9dR((LdL8cCYoZcJBe><tQ_?%yIR-+xp*1@$No8lpShTWe6&%_M=q!sfS)Sh8%Bix86'
    '%Cf61=|yLdBqYf1;P=mY2NbSqYnYE|2W3t6@EeQeJYL`eZoElmn$bw+L#fBsSm@^Pe)6QN>kK9~$y#Q?dolvpVhue7(K@s2Motzj'
    'p74kIRXbW877wwYR9eHIw3u1lXJ03%yEUKSXL<x@eFTE7ZEfE_V6FuD+%iwl`rEFq7+CWSsFctsBe9tiD5D>F`Ome(Okvgo&pKH('
    '2?)NWL>~=rsAChBa7U1&LtCoikRXLxpTSD%6Wul@w}k57Y9jJLNf`Y8-qrQ9rJoZu5qGHJC6_SWbON_L<g-cjQ9Qa_5{n$ERg+R5'
    'grGW%?SRvHy+uV3)n%Xe#L83*djtg$kUrh06zG2k?Mhiy5VR}g^;X!F0^b&tEQ9thNFc`ZFU{eH<?DVG@{LunWEjF__^=?oOb42G'
    'U(PXW-qU~et6ASDR9d)mwxAak29qtDM`HR}ZsszNi{%tef4yo-!%IPb%ilg%8Q8Y-$SPVZcW{ASRJMxF6DMNE4y%_7r;1anG@{f|'
    '#U>JpS3oe~mI+)AQI|4(u~EjH8lF8`E|KQDu!T=-5=z`?h72VonEk2V5om4BqP9x%--_M(HaS=_d-W2vL)a9oCqd{s(XCz8)hk3W'
    'Zhmp&)Np0|A?Ei~ki0EM=}Pi9WrRP=+#k55ag$XKcR49WCY!i0OM_RR8n8Z3B6;S^!ukMv_G4w63x*Z{&m!L^)za!>5!(D9=$lMP'
    '&8t%zZPl`x!eJ~CX@wkxT~L0@_Ic7E&8jwpZB3rME>^_0W5oLT%ILt`mHU||lq(l5DHrpIx;!|ix2noZEl;KUr5~!NredXSxTVIi'
    ';E_MaIJ{Abo1>NZmM_QNH-+BawbDEqwUl3yR<6t*$Prt*(^f5EE34?+EG2>p`PleS2H6E;RX$}lf*w3mGr#Kn{wy4NJlV%AZFV(z'
    'sg;S)`DPkl8nj5YeTB3FFP>3d`uzO`%%RKfJE-4t=NMzE^O6rFQauZYk2-MQlb0EC94~RTMAGo;_t&w{lS0E$W%oTj?o^wik%sjE'
    'A9wbf-_tD8T&}aWeG|B1J+A4YT)qap9ypw5!pisD#-DLwGJn>n?>T#D+rNr$r9;0rRVwj_A3~`fMHcX9{iE0xuea&DP^6f(cWNiy'
    'm%9_*JU0#{eKY`Pb`g!vFWN-3I)$Chyp0iY5_X23DKVzXvz>e8P@Y-+;l<8;t_0E-m)3L6zCBlk2>j9)`6t&h`x^3XpBizDq*5i;'
    '?4H3f=5+4i7>6$L5@1d|%CTIQRpS8hBhpP>?ur)i_3>>VCGf~EH5+$uT)QFkG`D~IYu=~Fo^VGE<7yOHHTJCE<<#i2XUy5jU{nQz'
    'g<I%-?x_&J-hYajy~(jcmQ`&>_oH%L?x?Bm=l{n2Vna{yFl&LD-R!ytniyZJD7vbgNAUPn6-YJmUMSr^r6ojpk1@{$9Bcon&agPP'
    'f)9Zz9{Rq`Pt+Bpyw3L<9ab9~9Bs5je7fYguJZ{R5<265aNq>u|Bf)D=!AX0+p1B4<*U5kBlhm&d`h86L*wqf|B&UTtb-Hrswi-T'
    'cOrB7FKYz|dbUf9xmWz~fN?rz6dVNKU=faTN!CaN97x+3QD0lMR}bNTNQ9W&9)>33mm2iDe<x8Al7oc36OqFti{$K)+_rD^!)E24'
    'POYlxkWl9Mn*R-7ogn<Q!)DlX((#Ib$yEK*0hsc~7{syVd&Q7sB!J0#CcWx1$NT!+y55%Lj_ax1LK}OZsOTN#;!UcZDU)rTPWHa1'
    'RbFO-5q)0T<;)tp;%=6Ma+3t*qE5ZWe{dF|u*_f#-+u*kdV?_U&P*7!^ah6iR%(C`I(@N|WZfWoky=ke)OZ;E(8rO=@cfrlgnpOg'
    'HSB%<3mT|)ttpbLM_@VyMnCiQ48`1aWYW)^xn1P8z|i~5okIK#^}_H`kv~bKnRnDDJuSAKL=80P=V_5GTdI;sQq**krUdLuDs`ke'
    'BxR{HQGK@{r22u%;5P7QK^4PgtWm7v*pyX_261xXXIN*1Ii465g<S%bjP{mL$QZC<fx~0s2sZM;y(JnlP6`FXaou$4Vd-}kIsb*P'
    'EP}6Y?^vG8S&fep^7xWIm*l4xvy@?dJiSkwpwVNDZ%V55fkuhEaLMW{de#hP^;*O1_L^0dX-xb|<})8o9NJ%iPK{h~0qfIPO8!a)'
    '<5L(Mae8mkV;h|cY2)z71SEaB>zG91wT{hJ=pHSPH-&3%D(b8a@RbR?pDNsN-30xgN#AYbLd$G{!6E5cDf~+jNEJPo(%=P4K80Y?'
    '{h<5i$S@LBsyy7QBpGRfSY97HCFGj0-OVjmqgl$7vkX#|lyL21=k<?mU<ffckb3_De5X2spD$uDz98sU?wIKD-=s!&z4|fG!96wq'
    'Y&n+j%(}0`sJ;5S55}&b^Jh&&TXi3)efa@``y5vEy3YUk<!xRZ^PY#Tx|MWe_s$y|VBLnPU%>S=JE2-Soq2h(>WS;tuP4Vnv|oLF'
    'YsV+-F{Ynj(B+g0u72zs+ifK-lU4^HG8G2jB7@11I&1m4_<*eHBdouk(z+0nj>GT=2I*IV!@t3#dpqmrV$xCNi0;=U^q^Cny89e9'
    '$XOls@b?<W&quTtB=S~v<S^#3#oB8rGOC9)Ykc-u`?UwA)$NMjnIITBqV#r%Gt9c8b24M8P`yIz=!*2H2OaJWFzk-s-h#A7Ol^T%'
    'Kb+jkpw6xR$+t&Wb=ufoo@)5ifJ8my#6?@Nr9Qm>SFwn^w@9)R=F4>duI^EX1Wl9%r}S9vU@OU1$6R8zzRTKrSAhAy`9+qB@k#v-'
    'Mi}ohL3YiQt})oY9~GVU$-NVt+9s&?ni(bllEhEx9;T1^J?e=@>O)H6;@(_V+Sc^U-z`j0yqUUYn-Ds89pRDQDamI6)avZ0cQ8qs'
    'EfBQ5OL^+~>VsYlRT^$HohP=|&L!gQe`K^Wp|pePer;?4^S<Q*M$+tov*Y{Iu9_0nJR*SGzCDIw`EG$x-hQV6h(JhPItjESOst3S'
    'f4SB6CbJg194lulPCR*djO}dIgU_?BuC6hrd1)b$cGzWJw0q%zM5Q$FjcrhvTBDXd>fewY;vlDl(9c)@H`fhJYW`xRM!_uOMwb}R'
    'WInQ!9~cuWRNZ%Q!Xl|O&kzhSu(ur3nhW^(pX;9>e)njC8W^Q6oZ8s0(Y(8>YI71j?+qKd;^m+AJDeXpR|3bVr<@5JWa}AH&b<;z'
    '6*nB1?n_6laa$5Tx(osB#^0L_dK=e=THm`0j;SZT@4wLg9btNmAGT?P{`J>n<A+~ryhtqfht546%q3<qu2Fu>7B^?$y=hjzvfna)'
    'me3Q-;amSD{m#zSo;twdW6WquX`1%7`Z(m_Fy!Gd<l!*n;V|UkFy!Gd<l!*n;V|UkFy!Gd<l!*n;V|UkFy!Gd<l*oi>*4VKF*W<O'
)

FONT_TABLE = {'mast': {'g': {' ': (928, 0, 52, 15, 0, 0), '!': (1236, 0, 14, 19, 39, 0), '"': (2061, 0, 14, 32, 38, 741), '#': (1856, 0, 14, 29, 38, 1957), '$': (1856, 0, 9, 29, 48, 3059), '%': (3712, 0, 13, 58, 40, 4451), '&': (3092, 0, 13, 48, 40, 6771), "'": (1031, 0, 14, 16, 38, 8691), '(': (1236, 0, 12, 19, 52, 9299), ')': (1236, 0, 12, 19, 52, 10287), '*': (1856, 0, 14, 29, 38, 11275), '+': (2115, 0, 19, 33, 33, 12377), ',': (928, 0, 43, 15, 18, 13466), '-': (1236, 0, 36, 19, 16, 13736), '.': (928, 0, 44, 15, 9, 14040), '/': (1031, -1, 13, 18, 40, 14175), '0': (1856, 0, 13, 29, 40, 14895), '1': (1856, 0, 14, 29, 38, 16055), '2': (1856, 0, 13, 29, 39, 17157), '3': (1856, 0, 13, 29, 40, 18288), '4': (1856, 0, 14, 29, 38, 19448), '5': (1856, 0, 14, 29, 39, 20550), '6': (1856, 0, 13, 29, 40, 21681), '7': (1856, 0, 14, 29, 38, 22841), '8': (1856, 0, 13, 29, 40, 23943), '9': (1856, 0, 13, 29, 40, 25103), ':': (1236, 0, 24, 19, 29, 26263), ';': (1236, 0, 24, 19, 37, 26814), '<': (2115, 0, 18, 33, 34, 27517), '=': (2115, 0, 25, 33, 27, 28639), '>': (2115, 0, 18, 33, 34, 29530), '?': (1856, 0, 13, 29, 40, 30652), '@': (3453, 0, 13, 54, 50, 31812), 'A': (2681, 0, 13, 42, 39, 34512), 'B': (2476, 0, 14, 39, 39, 36150), 'C': (2681, 0, 13, 42, 40, 37671), 'D': (2681, 0, 14, 42, 39, 39351), 'E': (2476, 0, 14, 39, 38, 40989), 'F': (2267, 0, 14, 35, 38, 42471), 'G': (2887, 0, 13, 45, 40, 43801), 'H': (2887, 0, 14, 45, 38, 45601), 'I': (1445, 0, 14, 23, 38, 47311), 'J': (1856, 0, 14, 29, 39, 48185), 'K': (2887, 0, 14, 45, 38, 49316), 'L': (2476, 0, 14, 39, 38, 51026), 'M': (3504, 0, 14, 55, 38, 52508), 'N': (2681, 0, 14, 42, 38, 54598), 'O': (2887, 0, 13, 45, 40, 56194), 'P': (2267, 0, 14, 35, 38, 57994), 'Q': (2887, 0, 13, 45, 49, 59324), 'R': (2681, 0, 14, 43, 38, 61529), 'S': (2064, 0, 13, 32, 40, 63163), 'T': (2476, 0, 14, 39, 38, 64443), 'U': (2681, 0, 14, 42, 39, 65925), 'V': (2681, 0, 14, 42, 39, 67563), 'W': (3712, 0, 14, 58, 39, 69201), 'X': (2681, 0, 14, 42, 38, 71463), 'Y': (2681, 0, 14, 42, 38, 73059), 'Z': (2476, 0, 14, 39, 38, 74655), '[': (1236, 0, 12, 19, 48, 76137), '\\': (1031, -1, 13, 18, 40, 77049), ']': (1236, 0, 12, 19, 48, 77769), '^': (2157, 0, 14, 34, 38, 78681), '_': (1856, -1, 52, 31, 9, 79973), '`': (1236, 0, 11, 19, 41, 80252), 'a': (1856, 0, 24, 29, 29, 81031), 'b': (2064, 0, 12, 32, 41, 81872), 'c': (1648, 0, 24, 26, 29, 83184), 'd': (2064, 0, 12, 32, 41, 83938), 'e': (1648, 0, 24, 26, 29, 85250), 'f': (1236, 0, 11, 20, 41, 86004), 'g': (1856, 0, 21, 29, 43, 86824), 'h': (2064, 0, 12, 32, 40, 88071), 'i': (1031, 0, 11, 16, 41, 89351), 'j': (1236, -1, 11, 20, 53, 90007), 'k': (2064, 0, 12, 33, 40, 91067), 'l': (1031, 0, 12, 16, 40, 92387), 'm': (3092, 0, 24, 48, 28, 93027), 'n': (2064, 0, 24, 32, 28, 94371), 'o': (1856, 0, 24, 29, 29, 95267), 'p': (2064, 0, 24, 32, 40, 96108), 'q': (2064, 0, 23, 32, 41, 97388), 'r': (1648, 0, 24, 26, 28, 98700), 's': (1445, 0, 24, 23, 29, 99428), 't': (1236, 0, 19, 20, 34, 100095), 'u': (2064, 0, 25, 32, 28, 100775), 'v': (1856, 0, 25, 29, 28, 101671), 'w': (2681, 0, 25, 42, 28, 102483), 'x': (1856, 0, 25, 29, 27, 103659), 'y': (1856, 0, 25, 29, 39, 104442), 'z': (1648, 0, 25, 26, 27, 105573), '{': (1463, 0, 12, 23, 48, 106275), '|': (817, 0, 12, 13, 52, 107379), '}': (1463, 0, 12, 23, 48, 108055), '~': (1930, 0, 27, 30, 25, 109159), '£': (1856, 0, 13, 29, 39, 109909), '°': (1484, 0, 13, 23, 39, 111040), '·': (1238, 0, 28, 19, 24, 111937), 'à': (1856, 0, 11, 29, 42, 112393), 'á': (1856, 0, 11, 29, 42, 113611), 'ç': (1648, 0, 24, 26, 40, 114829), 'é': (1648, 0, 11, 26, 42, 115869), 'í': (1031, 0, 11, 17, 41, 116961), 'ñ': (2064, 0, 11, 32, 41, 117658), 'ü': (2064, 0, 13, 32, 40, 118970), '–': (1856, -1, 36, 31, 16, 120250), '—': (3712, -1, 36, 60, 16, 120746), '‘': (1236, 0, 13, 19, 39, 121706), '’': (1236, 0, 13, 19, 39, 122447), '“': (1856, 0, 13, 29, 39, 123188), '”': (1856, 0, 13, 29, 39, 124319), '•': (1300, 0, 25, 20, 27, 125450), '…': (3712, 0, 44, 58, 9, 125990), '€': (1856, 0, 13, 29, 40, 126512), '−': (2115, 0, 31, 33, 21, 127672), '▲': (3674, 0, 18, 57, 34, 128365)}, 'k': {' A': -205, ' T': -67, ' V': -67, ' W': -67, ' Y': -138, 'A ': -205, 'AT': -275, 'F ': -138, 'L ': -205, 'LY': -341, 'P ': -205, 'PA': -275, 'T ': -67, 'V ': -67, 'W ': -67, 'Y ': -138, 'r ': -67, '’ ': -275}}, 'date': {'g': {' ': (302, 0, 16, 5, 0, 130303), '!': (362, 0, 4, 6, 12, 130303), '"': (516, 0, 4, 8, 12, 130375), '#': (605, 0, 4, 10, 12, 130471), '$': (605, 0, 2, 10, 16, 130591), '%': (967, 0, 4, 15, 12, 130751), '&': (786, 0, 4, 12, 12, 130931), "'": (259, 0, 4, 4, 12, 131075), '(': (362, 0, 4, 6, 16, 131123), ')': (362, 0, 4, 6, 16, 131219), '*': (423, 0, 4, 7, 12, 131315), '+': (635, 0, 5, 10, 11, 131399), ',': (302, 0, 14, 5, 5, 131509), '-': (362, 0, 11, 6, 5, 131534), '.': (302, 0, 14, 5, 2, 131564), '/': (302, 0, 4, 5, 12, 131574), '0': (605, 0, 4, 9, 12, 131634), '1': (605, 0, 4, 9, 12, 131742), '2': (605, 0, 4, 9, 12, 131850), '3': (605, 0, 4, 9, 12, 131958), '4': (605, 0, 4, 10, 12, 132066), '5': (605, 0, 4, 9, 12, 132186), '6': (605, 0, 4, 9, 12, 132294), '7': (605, 0, 4, 9, 12, 132402), '8': (605, 0, 4, 9, 12, 132510), '9': (605, 0, 4, 9, 12, 132618), ':': (362, 0, 7, 6, 9, 132726), ';': (362, 0, 7, 6, 12, 132780), '<': (635, 0, 6, 10, 10, 132852), '=': (635, 0, 7, 10, 9, 132952), '>': (635, 0, 6, 10, 10, 133042), '?': (665, 0, 4, 10, 12, 133142), '@': (1061, 0, 4, 17, 15, 133262), 'A': (786, 0, 4, 12, 12, 133517), 'B': (786, 0, 4, 12, 12, 133661), 'C': (786, 0, 4, 12, 12, 133805), 'D': (786, 0, 4, 12, 12, 133949), 'E': (726, 0, 4, 11, 12, 134093), 'F': (665, 0, 4, 10, 12, 134225), 'G': (846, 0, 4, 13, 12, 134345), 'H': (786, 0, 4, 12, 12, 134501), 'I': (302, 0, 4, 5, 12, 134645), 'J': (605, 0, 4, 9, 12, 134705), 'K': (786, 0, 4, 13, 12, 134813), 'L': (665, 0, 4, 10, 12, 134969), 'M': (906, 0, 4, 14, 12, 135089), 'N': (786, 0, 4, 12, 12, 135257), 'O': (846, 0, 4, 13, 12, 135401), 'P': (726, 0, 4, 11, 12, 135557), 'Q': (846, 0, 4, 13, 15, 135689), 'R': (786, 0, 4, 12, 12, 135884), 'S': (726, 0, 4, 11, 12, 136028), 'T': (665, 0, 4, 11, 12, 136160), 'U': (786, 0, 4, 12, 12, 136292), 'V': (726, 0, 4, 12, 12, 136436), 'W': (1027, 0, 4, 17, 12, 136580), 'X': (726, 0, 4, 12, 12, 136784), 'Y': (726, 0, 4, 12, 12, 136928), 'Z': (665, 0, 4, 10, 12, 137072), '[': (362, 0, 4, 6, 16, 137192), '\\': (302, 0, 4, 5, 12, 137288), ']': (362, 0, 4, 6, 16, 137348), '^': (635, 0, 4, 10, 12, 137444), '_': (605, -1, 16, 11, 2, 137564), '`': (362, 0, 3, 6, 13, 137586), 'a': (605, 0, 7, 10, 9, 137664), 'b': (665, 0, 4, 10, 12, 137754), 'c': (605, 0, 7, 9, 9, 137874), 'd': (665, 0, 4, 10, 12, 137955), 'e': (605, 0, 7, 9, 9, 138075), 'f': (362, 0, 4, 6, 12, 138156), 'g': (665, 0, 7, 10, 13, 138228), 'h': (665, 0, 4, 10, 12, 138358), 'i': (302, 0, 4, 5, 12, 138478), 'j': (302, -1, 4, 6, 16, 138538), 'k': (605, 0, 4, 10, 12, 138634), 'l': (302, 0, 4, 5, 12, 138754), 'm': (967, 0, 7, 15, 9, 138814), 'n': (665, 0, 7, 10, 9, 138949), 'o': (665, 0, 7, 10, 9, 139039), 'p': (665, 0, 7, 10, 13, 139129), 'q': (665, 0, 7, 10, 13, 139259), 'r': (423, 0, 7, 7, 9, 139389), 's': (605, 0, 7, 9, 9, 139452), 't': (362, 0, 5, 6, 11, 139533), 'u': (665, 0, 7, 10, 9, 139599), 'v': (605, 0, 7, 10, 9, 139689), 'w': (846, -1, 7, 15, 9, 139779), 'x': (605, 0, 7, 10, 9, 139914), 'y': (605, 0, 7, 10, 13, 140004), 'z': (544, 0, 7, 9, 9, 140134), '{': (423, 0, 4, 7, 16, 140215), '|': (304, 0, 4, 5, 16, 140327), '}': (423, 0, 4, 7, 16, 140407), '~': (635, 0, 8, 10, 8, 140519), '£': (605, 0, 4, 10, 12, 140599), '°': (435, 0, 4, 7, 12, 140719), '·': (362, 0, 9, 6, 7, 140803), 'à': (605, 0, 3, 10, 13, 140845), 'á': (605, 0, 3, 10, 13, 140975), 'ç': (605, 0, 7, 9, 13, 141105), 'é': (605, 0, 3, 9, 13, 141222), 'í': (302, 0, 3, 6, 13, 141339), 'ñ': (665, 0, 3, 10, 13, 141417), 'ü': (665, 0, 4, 10, 12, 141547), '–': (605, 0, 11, 9, 5, 141667), '—': (1088, 0, 11, 17, 5, 141712), '‘': (302, 0, 4, 5, 12, 141797), '’': (302, 0, 4, 5, 12, 141857), '“': (544, 0, 4, 9, 12, 141917), '”': (544, 0, 4, 9, 12, 142025), '•': (381, 0, 8, 6, 8, 142133), '…': (1088, 0, 14, 17, 2, 142181), '€': (605, 0, 4, 10, 12, 142215), '−': (635, 0, 9, 10, 7, 142335), '▲': (1077, 0, 6, 17, 10, 142405)}, 'k': {' A': -40, ' Y': -20, 'A ': -40, 'L ': -20, 'P ': -20, 'Y ': -20, 'y,': -81, '’ ': -60}}, 'info': {'g': {' ': (196, 0, 10, 3, 0, 142575), '!': (196, 0, 2, 3, 8, 142575), '"': (250, 0, 2, 4, 8, 142599), '#': (392, 0, 2, 7, 8, 142631), '$': (392, 0, 1, 6, 10, 142687), '%': (626, 0, 2, 10, 8, 142747), '&': (470, 0, 2, 8, 8, 142827), "'": (134, 0, 2, 2, 8, 142891), '(': (234, 0, 2, 4, 10, 142907), ')': (234, 0, 2, 4, 10, 142947), '*': (274, 0, 2, 5, 8, 142987), '+': (411, 0, 3, 6, 7, 143027), ',': (196, 0, 9, 3, 3, 143069), '-': (234, 0, 6, 4, 4, 143078), '.': (196, 0, 9, 3, 1, 143094), '/': (196, 0, 2, 4, 8, 143097), '0': (392, 0, 2, 6, 8, 143129), '1': (392, 0, 2, 6, 8, 143177), '2': (392, 0, 2, 6, 8, 143225), '3': (392, 0, 2, 6, 8, 143273), '4': (392, 0, 2, 6, 8, 143321), '5': (392, 0, 2, 6, 8, 143369), '6': (392, 0, 2, 6, 8, 143417), '7': (392, 0, 2, 6, 8, 143465), '8': (392, 0, 2, 6, 8, 143513), '9': (392, 0, 2, 6, 8, 143561), ':': (196, 0, 4, 3, 6, 143609), ';': (196, 0, 4, 3, 8, 143627), '<': (411, 0, 4, 6, 6, 143651), '=': (411, 0, 5, 6, 5, 143687), '>': (411, 0, 4, 6, 6, 143717), '?': (392, 0, 2, 6, 8, 143753), '@': (715, 0, 2, 11, 10, 143801), 'A': (470, 0, 2, 8, 8, 143911), 'B': (470, 0, 2, 7, 8, 143975), 'C': (508, 0, 2, 8, 8, 144031), 'D': (508, 0, 2, 8, 8, 144095), 'E': (470, 0, 2, 7, 8, 144159), 'F': (430, 0, 2, 7, 8, 144215), 'G': (548, 0, 2, 9, 8, 144271), 'H': (508, 0, 2, 8, 8, 144343), 'I': (196, 0, 2, 3, 8, 144407), 'J': (352, 0, 2, 6, 8, 144431), 'K': (470, 0, 2, 8, 8, 144479), 'L': (392, 0, 2, 6, 8, 144543), 'M': (586, 0, 2, 9, 8, 144591), 'N': (508, 0, 2, 8, 8, 144663), 'O': (548, 0, 2, 9, 8, 144727), 'P': (470, 0, 2, 7, 8, 144799), 'Q': (548, 0, 2, 9, 10, 144855), 'R': (508, 0, 2, 8, 8, 144945), 'S': (470, 0, 2, 7, 8, 145009), 'T': (430, 0, 2, 7, 8, 145065), 'U': (508, 0, 2, 8, 8, 145121), 'V': (470, 0, 2, 8, 8, 145185), 'W': (664, 0, 2, 11, 8, 145249), 'X': (470, 0, 2, 8, 8, 145337), 'Y': (470, 0, 2, 8, 8, 145401), 'Z': (430, 0, 2, 7, 8, 145465), '[': (196, 0, 2, 3, 10, 145521), '\\': (196, 0, 2, 4, 8, 145551), ']': (196, 0, 2, 3, 10, 145583), '^': (330, 0, 2, 6, 8, 145613), '_': (392, -1, 10, 8, 2, 145661), '`': (234, 0, 1, 4, 9, 145677), 'a': (392, 0, 4, 7, 6, 145713), 'b': (392, 0, 2, 6, 8, 145755), 'c': (352, 0, 4, 6, 6, 145803), 'd': (392, 0, 2, 6, 8, 145839), 'e': (392, 0, 4, 6, 6, 145887), 'f': (196, 0, 2, 4, 8, 145923), 'g': (392, 0, 4, 6, 8, 145955), 'h': (392, 0, 2, 6, 8, 146003), 'i': (156, 0, 2, 2, 8, 146051), 'j': (156, -1, 2, 3, 10, 146067), 'k': (352, 0, 2, 6, 8, 146097), 'l': (156, 0, 2, 2, 8, 146145), 'm': (586, 0, 4, 9, 6, 146161), 'n': (392, 0, 4, 6, 6, 146215), 'o': (392, 0, 4, 6, 6, 146251), 'p': (392, 0, 4, 6, 8, 146287), 'q': (392, 0, 4, 6, 8, 146335), 'r': (234, 0, 4, 4, 6, 146383), 's': (352, 0, 4, 6, 6, 146407), 't': (196, 0, 3, 3, 7, 146443), 'u': (392, 0, 4, 6, 6, 146464), 'v': (352, 0, 4, 6, 6, 146500), 'w': (508, -1, 4, 9, 6, 146536), 'x': (352, 0, 4, 6, 6, 146590), 'y': (352, 0, 4, 6, 8, 146626), 'z': (352, 0, 4, 6, 6, 146674), '{': (235, 0, 2, 4, 10, 146710), '|': (183, 0, 2, 3, 10, 146750), '}': (235, 0, 2, 4, 10, 146780), '~': (411, 0, 5, 6, 5, 146820), '£': (392, 0, 2, 6, 8, 146850), '°': (282, 0, 2, 4, 8, 146898), '·': (234, 0, 6, 4, 4, 146930), 'à': (392, 0, 1, 7, 9, 146946), 'á': (392, 0, 1, 7, 9, 147009), 'ç': (352, 0, 4, 6, 9, 147072), 'é': (392, 0, 1, 6, 9, 147126), 'í': (196, 0, 1, 4, 9, 147180), 'ñ': (392, 0, 1, 6, 9, 147216), 'ü': (392, 0, 2, 6, 8, 147270), '–': (392, 0, 6, 7, 4, 147318), '—': (704, 0, 6, 11, 4, 147346), '‘': (156, 0, 2, 2, 8, 147390), '’': (156, 0, 2, 2, 8, 147406), '“': (234, 0, 2, 4, 8, 147422), '”': (234, 0, 2, 4, 8, 147454), '•': (246, 0, 5, 4, 5, 147486), '…': (704, 0, 9, 11, 1, 147506), '€': (392, 0, 2, 6, 8, 147517), '−': (411, 0, 6, 6, 4, 147565), '▲': (697, 0, 4, 11, 6, 147589)}, 'k': {' A': -39, ' T': -13, ' Y': -13, 'A ': -39, 'AY': -52, 'L ': -26, 'P ': -13, 'PA': -52, 'RY': -13, 'T ': -13, 'TO': -13, 'Vo': -39, 'Y ': -13, '’ ': -26}}, 'kicker': {'g': {' ': (231, 0, 12, 4, 0, 147655), '!': (277, 0, 2, 4, 10, 147655), '"': (394, 0, 2, 6, 10, 147695), '#': (463, 0, 2, 8, 10, 147755), '$': (463, 0, 1, 8, 13, 147835), '%': (740, 0, 2, 12, 10, 147939), '&': (601, 0, 2, 9, 10, 148059), "'": (198, 0, 2, 3, 10, 148149), '(': (277, 0, 2, 5, 13, 148179), ')': (277, 0, 2, 4, 13, 148244), '*': (324, 0, 2, 6, 10, 148296), '+': (486, 0, 4, 8, 8, 148356), ',': (231, 0, 10, 4, 4, 148420), '-': (277, 0, 8, 4, 4, 148436), '.': (231, 0, 10, 4, 2, 148452), '/': (231, 0, 2, 4, 10, 148460), '0': (463, 0, 2, 7, 10, 148500), '1': (463, 0, 2, 7, 10, 148570), '2': (463, 0, 2, 7, 10, 148640), '3': (463, 0, 2, 7, 10, 148710), '4': (463, 0, 2, 8, 10, 148780), '5': (463, 0, 2, 7, 10, 148860), '6': (463, 0, 2, 7, 10, 148930), '7': (463, 0, 2, 7, 10, 149000), '8': (463, 0, 2, 7, 10, 149070), '9': (463, 0, 2, 7, 10, 149140), ':': (277, 0, 5, 4, 7, 149210), ';': (277, 0, 5, 4, 9, 149238), '<': (486, 0, 4, 8, 8, 149274), '=': (486, 0, 6, 8, 6, 149338), '>': (486, 0, 4, 8, 8, 149386), '?': (508, 0, 2, 8, 10, 149450), '@': (811, 0, 2, 13, 12, 149530), 'A': (601, 0, 2, 10, 10, 149686), 'B': (601, 0, 2, 9, 10, 149786), 'C': (601, 0, 2, 10, 10, 149876), 'D': (601, 0, 2, 9, 10, 149976), 'E': (555, 0, 2, 9, 10, 150066), 'F': (508, 0, 2, 8, 10, 150156), 'G': (647, 0, 2, 10, 10, 150236), 'H': (601, 0, 2, 9, 10, 150336), 'I': (231, 0, 2, 4, 10, 150426), 'J': (463, 0, 2, 7, 10, 150466), 'K': (601, 0, 2, 10, 10, 150536), 'L': (508, 0, 2, 8, 10, 150636), 'M': (693, 0, 2, 11, 10, 150716), 'N': (601, 0, 2, 9, 10, 150826), 'O': (647, 0, 2, 10, 10, 150916), 'P': (555, 0, 2, 9, 10, 151016), 'Q': (647, 0, 2, 10, 13, 151106), 'R': (601, 0, 2, 10, 10, 151236), 'S': (555, 0, 2, 9, 10, 151336), 'T': (508, 0, 2, 8, 10, 151426), 'U': (601, 0, 2, 9, 10, 151506), 'V': (555, 0, 2, 9, 10, 151596), 'W': (785, 0, 2, 13, 10, 151686), 'X': (555, 0, 2, 9, 10, 151816), 'Y': (555, 0, 2, 9, 10, 151906), 'Z': (508, 0, 2, 8, 10, 151996), '[': (277, 0, 2, 5, 13, 152076), '\\': (231, 0, 2, 4, 10, 152141), ']': (277, 0, 2, 4, 13, 152181), '^': (486, 0, 2, 8, 10, 152233), '_': (463, -1, 12, 9, 2, 152313), '`': (277, 0, 1, 4, 11, 152331), 'a': (463, 0, 5, 8, 7, 152375), 'b': (508, 0, 2, 8, 10, 152431), 'c': (463, 0, 5, 7, 7, 152511), 'd': (508, 0, 2, 8, 10, 152560), 'e': (463, 0, 5, 7, 7, 152640), 'f': (277, 0, 2, 5, 10, 152689), 'g': (508, 0, 5, 8, 10, 152739), 'h': (508, 0, 2, 8, 10, 152819), 'i': (231, 0, 2, 4, 10, 152899), 'j': (231, -1, 2, 5, 13, 152939), 'k': (463, 0, 2, 8, 10, 153004), 'l': (231, 0, 2, 4, 10, 153084), 'm': (740, 0, 5, 12, 7, 153124), 'n': (508, 0, 5, 8, 7, 153208), 'o': (508, 0, 5, 8, 7, 153264), 'p': (508, 0, 5, 8, 10, 153320), 'q': (508, 0, 5, 8, 10, 153400), 'r': (324, 0, 5, 5, 7, 153480), 's': (463, 0, 5, 7, 7, 153515), 't': (277, 0, 3, 5, 9, 153564), 'u': (508, 0, 5, 8, 7, 153609), 'v': (463, 0, 5, 8, 7, 153665), 'w': (647, -1, 5, 12, 7, 153721), 'x': (463, 0, 5, 8, 7, 153805), 'y': (463, 0, 5, 8, 10, 153861), 'z': (416, 0, 5, 7, 7, 153941), '{': (324, 0, 2, 5, 13, 153990), '|': (233, 0, 2, 4, 13, 154055), '}': (324, 0, 2, 5, 13, 154107), '~': (486, 0, 7, 8, 5, 154172), '£': (463, 0, 2, 8, 10, 154212), '°': (333, 0, 2, 5, 10, 154292), '·': (277, 0, 7, 4, 5, 154342), 'à': (463, 0, 1, 8, 11, 154362), 'á': (463, 0, 1, 8, 11, 154450), 'ç': (463, 0, 5, 7, 10, 154538), 'é': (463, 0, 1, 7, 11, 154608), 'í': (231, 0, 1, 4, 11, 154685), 'ñ': (508, 0, 2, 8, 10, 154729), 'ü': (508, 0, 2, 8, 10, 154809), '–': (463, 0, 8, 7, 4, 154889), '—': (832, 0, 8, 13, 4, 154917), '‘': (231, 0, 2, 4, 10, 154969), '’': (231, 0, 2, 4, 10, 155009), '“': (416, 0, 2, 7, 10, 155049), '”': (416, 0, 2, 7, 10, 155119), '•': (291, 0, 6, 5, 6, 155189), '…': (832, 0, 10, 13, 2, 155219), '€': (463, 0, 2, 7, 10, 155245), '−': (486, 0, 7, 8, 5, 155315), '▲': (823, 0, 4, 13, 8, 155355)}, 'k': {' A': -31, ' Y': -15, 'A ': -31, 'AT': -62, 'AY': -76, 'L ': -15, 'LT': -62, 'LY': -76, 'P ': -15, 'PA': -62, 'TA': -62, 'Y ': -15, 'YA': -76, '’ ': -46}}, 'hero': {'g': {' ': (528, 0, 30, 8, 0, 155459), '!': (703, 0, 8, 11, 22, 155459), '"': (1173, 0, 8, 18, 22, 155701), '#': (1056, 0, 8, 17, 22, 156097), '$': (1056, 0, 6, 17, 26, 156471), '%': (2112, 0, 8, 33, 22, 156913), '&': (1759, 0, 8, 27, 22, 157639), "'": (587, 0, 8, 9, 22, 158233), '(': (703, 0, 7, 11, 30, 158431), ')': (703, 0, 7, 11, 30, 158761), '*': (1056, 0, 8, 17, 22, 159091), '+': (1203, 0, 11, 19, 19, 159465), ',': (528, 0, 25, 8, 10, 159826), '-': (703, 0, 21, 11, 9, 159906), '.': (528, 0, 25, 8, 5, 160005), '/': (587, -1, 8, 11, 22, 160045), '0': (1056, 0, 8, 17, 22, 160287), '1': (1056, 0, 8, 17, 22, 160661), '2': (1056, 0, 8, 17, 22, 161035), '3': (1056, 0, 8, 17, 22, 161409), '4': (1056, 0, 8, 17, 22, 161783), '5': (1056, 0, 8, 17, 22, 162157), '6': (1056, 0, 8, 17, 22, 162531), '7': (1056, 0, 8, 17, 22, 162905), '8': (1056, 0, 8, 17, 22, 163279), '9': (1056, 0, 8, 17, 22, 163653), ':': (703, 0, 15, 11, 15, 164027), ';': (703, 0, 15, 11, 20, 164192), '<': (1203, 0, 11, 19, 19, 164412), '=': (1203, 0, 15, 19, 15, 164773), '>': (1203, 0, 11, 19, 19, 165058), '?': (1056, 0, 8, 17, 22, 165419), '@': (1965, 0, 8, 31, 28, 165793), 'A': (1525, 0, 8, 24, 22, 166661), 'B': (1409, 0, 8, 22, 23, 167189), 'C': (1525, 0, 8, 24, 22, 167695), 'D': (1525, 0, 8, 24, 23, 168223), 'E': (1409, 0, 8, 22, 22, 168775), 'F': (1290, 0, 8, 20, 22, 169259), 'G': (1643, 0, 8, 26, 22, 169699), 'H': (1643, 0, 8, 26, 22, 170271), 'I': (822, 0, 8, 13, 22, 170843), 'J': (1056, 0, 8, 17, 22, 171129), 'K': (1643, 0, 8, 26, 22, 171503), 'L': (1409, 0, 8, 22, 22, 172075), 'M': (1993, 0, 8, 31, 22, 172559), 'N': (1525, 0, 8, 24, 22, 173241), 'O': (1643, 0, 8, 26, 22, 173769), 'P': (1290, 0, 8, 20, 22, 174341), 'Q': (1643, 0, 8, 26, 27, 174781), 'R': (1525, 0, 8, 25, 22, 175483), 'S': (1175, 0, 8, 18, 22, 176033), 'T': (1409, 0, 8, 22, 22, 176429), 'U': (1525, 0, 8, 24, 22, 176913), 'V': (1525, 0, 8, 24, 22, 177441), 'W': (2112, 0, 8, 33, 22, 177969), 'X': (1525, 0, 8, 24, 22, 178695), 'Y': (1525, 0, 8, 24, 22, 179223), 'Z': (1409, 0, 8, 22, 22, 179751), '[': (703, 0, 7, 11, 27, 180235), '\\': (587, -1, 8, 11, 22, 180532), ']': (703, 0, 7, 11, 27, 180774), '^': (1227, 0, 8, 19, 22, 181071), '_': (1056, -1, 30, 18, 5, 181489), '`': (703, 0, 7, 11, 23, 181579), 'a': (1056, 0, 15, 17, 15, 181832), 'b': (1175, 0, 7, 18, 23, 182087), 'c': (937, 0, 15, 15, 15, 182501), 'd': (1175, 0, 7, 18, 23, 182726), 'e': (937, 0, 15, 15, 15, 183140), 'f': (703, 0, 7, 12, 23, 183365), 'g': (1056, 0, 13, 17, 24, 183641), 'h': (1175, 0, 7, 18, 23, 184049), 'i': (587, 0, 7, 9, 23, 184463), 'j': (703, -1, 7, 12, 30, 184670), 'k': (1175, 0, 7, 19, 23, 185030), 'l': (587, 0, 7, 9, 23, 185467), 'm': (1759, 0, 15, 27, 15, 185674), 'n': (1175, 0, 15, 18, 15, 186079), 'o': (1056, 0, 15, 17, 15, 186349), 'p': (1175, 0, 15, 18, 22, 186604), 'q': (1175, 0, 14, 19, 23, 187000), 'r': (937, 0, 15, 15, 15, 187437), 's': (822, 0, 15, 13, 15, 187662), 't': (703, 0, 12, 11, 18, 187857), 'u': (1175, 0, 15, 18, 15, 188055), 'v': (1056, 0, 15, 17, 15, 188325), 'w': (1525, 0, 15, 24, 15, 188580), 'x': (1056, 0, 15, 17, 15, 188940), 'y': (1056, 0, 15, 17, 22, 189195), 'z': (937, 0, 15, 15, 15, 189569), '{': (832, 0, 7, 13, 27, 189794), '|': (465, 0, 7, 7, 30, 190145), '}': (832, 0, 7, 13, 27, 190355), '~': (1098, 0, 16, 17, 14, 190706), '£': (1056, 0, 8, 17, 22, 190944), '°': (845, 0, 8, 13, 22, 191318), '·': (704, 0, 16, 11, 14, 191604), 'à': (1056, 0, 7, 17, 23, 191758), 'á': (1056, 0, 7, 17, 23, 192149), 'ç': (937, 0, 15, 15, 22, 192540), 'é': (937, 0, 7, 15, 23, 192870), 'í': (587, 0, 7, 10, 23, 193215), 'ñ': (1175, 0, 7, 18, 23, 193445), 'ü': (1175, 0, 8, 18, 22, 193859), '–': (1056, -1, 21, 18, 9, 194255), '—': (2112, -1, 21, 35, 9, 194417), '‘': (703, 0, 8, 11, 22, 194732), '’': (703, 0, 8, 11, 22, 194974), '“': (1056, 0, 8, 17, 22, 195216), '”': (1056, 0, 8, 17, 22, 195590), '•': (739, 0, 15, 12, 15, 195964), '…': (2112, 0, 25, 33, 5, 196144), '€': (1056, 0, 8, 17, 22, 196309), '−': (1203, 0, 18, 19, 12, 196683), '▲': (2090, 0, 11, 33, 19, 196911)}, 'k': {' A': -117, ' T': -38, ' V': -38, ' W': -38, ' Y': -78, 'A ': -117, 'F ': -78, 'L ': -117, 'P ': -117, 'RT': -74, 'T ': -38, 'TA': -157, 'TO': -38, 'V ': -38, 'W ': -38, 'Y ': -78, 'r ': -38, '’ ': -157}}, 'hero_sum': {'g': {' ': (208, 0, 12, 3, 0, 197538), '!': (277, 0, 3, 4, 9, 197538), '"': (340, 0, 3, 5, 9, 197574), '#': (416, 0, 3, 7, 9, 197619), '$': (416, 0, 2, 7, 11, 197682), '%': (693, 0, 3, 11, 9, 197759), '&': (647, 0, 3, 10, 9, 197858), "'": (150, 0, 3, 2, 9, 197948), '(': (277, 0, 3, 4, 12, 197966), ')': (277, 0, 3, 4, 12, 198014), '*': (416, 0, 3, 7, 9, 198062), '+': (469, 0, 4, 7, 8, 198125), ',': (208, 0, 11, 3, 3, 198181), '-': (277, 0, 8, 4, 4, 198190), '.': (208, 0, 11, 3, 1, 198206), '/': (231, 0, 3, 4, 9, 198209), '0': (416, 0, 3, 7, 9, 198245), '1': (416, 0, 3, 7, 9, 198308), '2': (416, 0, 3, 7, 9, 198371), '3': (416, 0, 3, 7, 9, 198434), '4': (416, 0, 3, 7, 9, 198497), '5': (416, 0, 3, 7, 9, 198560), '6': (416, 0, 3, 7, 9, 198623), '7': (416, 0, 3, 7, 9, 198686), '8': (416, 0, 3, 7, 9, 198749), '9': (416, 0, 3, 7, 9, 198812), ':': (231, 0, 6, 4, 6, 198875), ';': (231, 0, 6, 4, 8, 198899), '<': (469, 0, 4, 7, 8, 198931), '=': (469, 0, 5, 7, 7, 198987), '>': (469, 0, 4, 7, 8, 199036), '?': (369, 0, 3, 6, 9, 199092), '@': (766, 0, 3, 12, 11, 199146), 'A': (601, 0, 3, 10, 9, 199278), 'B': (555, 0, 3, 9, 9, 199368), 'C': (555, 0, 3, 9, 9, 199449), 'D': (601, 0, 3, 9, 9, 199530), 'E': (508, 0, 3, 8, 9, 199611), 'F': (463, 0, 3, 7, 9, 199683), 'G': (601, 0, 3, 9, 9, 199746), 'H': (601, 0, 3, 9, 9, 199827), 'I': (277, 0, 3, 4, 9, 199908), 'J': (324, 0, 3, 5, 9, 199944), 'K': (601, 0, 3, 10, 9, 199989), 'L': (508, 0, 3, 8, 9, 200079), 'M': (740, 0, 3, 12, 9, 200151), 'N': (601, 0, 3, 10, 9, 200259), 'O': (601, 0, 3, 9, 9, 200349), 'P': (463, 0, 3, 7, 9, 200430), 'Q': (601, 0, 3, 10, 11, 200493), 'R': (555, 0, 3, 9, 9, 200603), 'S': (463, 0, 3, 7, 9, 200684), 'T': (508, 0, 3, 8, 9, 200747), 'U': (601, 0, 3, 10, 9, 200819), 'V': (601, 0, 3, 10, 9, 200909), 'W': (785, 0, 3, 13, 9, 200999), 'X': (601, 0, 3, 10, 9, 201116), 'Y': (601, 0, 3, 10, 9, 201206), 'Z': (508, 0, 3, 8, 9, 201296), '[': (277, 0, 3, 4, 11, 201368), '\\': (231, 0, 3, 4, 9, 201412), ']': (277, 0, 3, 4, 11, 201448), '^': (390, 0, 3, 6, 9, 201492), '_': (416, -1, 12, 8, 2, 201546), '`': (277, 0, 3, 4, 9, 201562), 'a': (369, 0, 6, 6, 6, 201598), 'b': (416, 0, 3, 7, 9, 201634), 'c': (369, 0, 6, 6, 6, 201697), 'd': (416, 0, 3, 7, 9, 201733), 'e': (369, 0, 6, 6, 6, 201796), 'f': (277, 0, 3, 5, 9, 201832), 'g': (416, 0, 5, 7, 10, 201877), 'h': (416, 0, 3, 7, 9, 201947), 'i': (231, 0, 3, 4, 9, 202010), 'j': (231, -1, 3, 5, 12, 202046), 'k': (416, 0, 3, 7, 9, 202106), 'l': (231, 0, 3, 4, 9, 202169), 'm': (647, 0, 6, 10, 6, 202205), 'n': (416, 0, 6, 7, 6, 202265), 'o': (416, 0, 6, 7, 6, 202307), 'p': (416, 0, 6, 7, 9, 202349), 'q': (416, 0, 5, 7, 10, 202412), 'r': (277, 0, 6, 5, 6, 202482), 's': (324, 0, 6, 5, 6, 202512), 't': (231, 0, 4, 4, 8, 202542), 'u': (416, 0, 6, 7, 6, 202574), 'v': (416, 0, 6, 7, 6, 202616), 'w': (601, 0, 6, 10, 6, 202658), 'x': (416, 0, 6, 7, 6, 202718), 'y': (416, 0, 6, 7, 9, 202760), 'z': (369, 0, 6, 6, 6, 202823), '{': (399, 0, 3, 6, 11, 202859), '|': (167, 0, 3, 3, 12, 202925), '}': (399, 0, 3, 6, 11, 202961), '~': (450, 0, 7, 7, 5, 203027), '£': (416, 0, 3, 7, 9, 203062), '°': (333, 0, 3, 5, 9, 203125), '·': (277, 0, 7, 4, 5, 203170), 'à': (369, 0, 3, 6, 9, 203190), 'á': (369, 0, 3, 6, 9, 203244), 'ç': (369, 0, 6, 6, 9, 203298), 'é': (369, 0, 3, 6, 9, 203352), 'í': (231, 0, 3, 4, 9, 203406), 'ñ': (416, 0, 3, 7, 9, 203442), 'ü': (416, 0, 3, 7, 9, 203505), '–': (416, -1, 8, 8, 4, 203568), '—': (832, -1, 8, 15, 4, 203600), '‘': (277, 0, 3, 4, 9, 203660), '’': (277, 0, 3, 4, 9, 203696), '“': (369, 0, 3, 6, 9, 203732), '”': (369, 0, 3, 6, 9, 203786), '•': (291, 0, 6, 5, 6, 203840), '…': (832, 0, 11, 13, 1, 203870), '€': (416, 0, 3, 7, 9, 203883), '−': (469, 0, 7, 7, 5, 203946), '▲': (823, 0, 4, 13, 8, 203981)}, 'k': {' A': -46, ' T': -15, ' V': -15, ' W': -15, ' Y': -31, 'A ': -46, 'L ': -31, 'LY': -83, 'P ': -31, 'T ': -15, 'TA': -67, 'V ': -15, 'W ': -15, 'Wo': -67, 'Y ': -31, 'YA': -92, '’ ': -62}}, 'byline': {'g': {' ': (192, 0, 11, 3, 0, 204085), '!': (256, 0, 2, 4, 9, 204085), '"': (323, 0, 2, 6, 9, 204121), '#': (384, 0, 2, 7, 9, 204175), '$': (384, 0, 1, 6, 11, 204238), '%': (640, 0, 2, 10, 9, 204304), '&': (597, 0, 2, 10, 9, 204394), "'": (164, 0, 2, 3, 9, 204484), '(': (256, 0, 2, 5, 12, 204511), ')': (256, -1, 2, 5, 12, 204571), '*': (384, 0, 2, 6, 9, 204631), '+': (518, 0, 4, 8, 7, 204685), ',': (192, 0, 10, 3, 3, 204741), '-': (256, 0, 8, 4, 3, 204750), '.': (192, 0, 10, 3, 1, 204762), '/': (213, -1, 2, 6, 9, 204765), '0': (384, 0, 2, 6, 9, 204819), '1': (384, 0, 2, 6, 9, 204873), '2': (384, 0, 2, 6, 9, 204927), '3': (384, -1, 2, 7, 9, 204981), '4': (384, 0, 2, 6, 9, 205044), '5': (384, 0, 2, 6, 9, 205098), '6': (384, 0, 2, 6, 9, 205152), '7': (384, 0, 2, 7, 9, 205206), '8': (384, 0, 2, 6, 9, 205269), '9': (384, 0, 2, 6, 9, 205323), ':': (256, 0, 5, 4, 6, 205377), ';': (256, 0, 5, 4, 8, 205401), '<': (518, 0, 4, 8, 7, 205433), '=': (518, 0, 6, 8, 5, 205489), '>': (518, 0, 4, 8, 7, 205529), '?': (384, 0, 2, 6, 9, 205585), '@': (707, 0, 2, 11, 11, 205639), 'A': (469, -1, 2, 9, 9, 205760), 'B': (469, 0, 2, 8, 9, 205841), 'C': (512, 0, 2, 9, 9, 205913), 'D': (555, -1, 2, 10, 10, 205994), 'E': (469, -1, 2, 9, 9, 206094), 'F': (469, -1, 2, 9, 9, 206175), 'G': (555, 0, 2, 9, 9, 206256), 'H': (555, -1, 2, 11, 9, 206337), 'I': (256, -1, 2, 6, 9, 206436), 'J': (341, 0, 2, 6, 9, 206490), 'K': (512, -1, 2, 10, 9, 206544), 'L': (427, -1, 2, 8, 9, 206634), 'M': (640, -1, 2, 12, 9, 206706), 'N': (512, -1, 2, 10, 9, 206814), 'O': (555, 0, 2, 9, 9, 206904), 'P': (469, -1, 2, 9, 9, 206985), 'Q': (555, 0, 2, 9, 11, 207066), 'R': (469, -1, 2, 9, 9, 207165), 'S': (384, 0, 2, 6, 9, 207246), 'T': (427, 0, 2, 8, 9, 207300), 'U': (555, 0, 2, 10, 9, 207372), 'V': (469, 0, 2, 9, 9, 207462), 'W': (640, 0, 2, 11, 9, 207543), 'X': (469, -1, 2, 9, 9, 207642), 'Y': (427, 0, 2, 8, 9, 207723), 'Z': (427, 0, 2, 7, 9, 207795), '[': (299, 0, 2, 6, 11, 207858), '\\': (213, 0, 2, 3, 9, 207924), ']': (299, -1, 2, 6, 11, 207951), '^': (324, 0, 2, 6, 9, 208017), '_': (384, -1, 11, 8, 2, 208071), '`': (256, 0, 2, 4, 9, 208087), 'a': (384, 0, 5, 6, 6, 208123), 'b': (384, 0, 2, 6, 9, 208159), 'c': (341, 0, 5, 6, 6, 208213), 'd': (384, 0, 2, 7, 9, 208249), 'e': (341, 0, 5, 6, 6, 208312), 'f': (213, 0, 2, 5, 12, 208348), 'g': (384, 0, 5, 6, 9, 208408), 'h': (384, 0, 2, 6, 9, 208462), 'i': (213, 0, 2, 3, 9, 208516), 'j': (213, -2, 2, 6, 12, 208543), 'k': (341, 0, 2, 6, 9, 208615), 'l': (213, 0, 2, 4, 9, 208669), 'm': (555, 0, 5, 9, 6, 208705), 'n': (384, 0, 5, 6, 6, 208759), 'o': (384, 0, 5, 6, 6, 208795), 'p': (384, -1, 5, 7, 9, 208831), 'q': (384, 0, 5, 6, 9, 208894), 'r': (299, 0, 5, 5, 6, 208948), 's': (299, 0, 5, 5, 6, 208978), 't': (213, 0, 4, 4, 7, 209008), 'u': (384, 0, 5, 6, 6, 209036), 'v': (341, 0, 5, 6, 6, 209072), 'w': (512, 0, 5, 8, 6, 209108), 'x': (341, -1, 5, 7, 6, 209156), 'y': (341, -1, 5, 7, 9, 209198), 'z': (299, -1, 5, 6, 6, 209261), '{': (307, 0, 2, 5, 11, 209297), '|': (211, 0, 2, 3, 12, 209352), '}': (307, 0, 2, 5, 11, 209388), '~': (416, 0, 6, 7, 5, 209443), '£': (384, 0, 2, 6, 9, 209478), '°': (307, 0, 2, 5, 9, 209532), '·': (192, 0, 7, 3, 4, 209577), 'à': (384, 0, 2, 6, 9, 209589), 'á': (384, 0, 2, 6, 9, 209643), 'ç': (341, 0, 5, 6, 9, 209697), 'é': (341, 0, 2, 6, 9, 209751), 'í': (213, 0, 2, 5, 9, 209805), 'ñ': (384, 0, 2, 6, 9, 209850), 'ü': (384, 0, 1, 6, 10, 209904), '–': (384, -1, 8, 8, 3, 209964), '—': (683, -1, 8, 12, 3, 209988), '‘': (256, 0, 2, 4, 9, 210024), '’': (256, 0, 2, 4, 9, 210060), '“': (427, 0, 2, 7, 9, 210096), '”': (427, 0, 2, 7, 9, 210159), '•': (269, 0, 5, 4, 6, 210222), '…': (683, 0, 10, 11, 1, 210246), '€': (384, 0, 2, 7, 9, 210257), '−': (518, 0, 7, 8, 4, 210320), '▲': (760, 0, 4, 12, 7, 210352)}, 'k': {' A': -14, 'A ': -14, 'L ': -14, 'P ': -14, 'T ': -14, 'V ': -14, '’ ': -85}}, 'caption': {'g': {' ': (176, 0, 10, 3, 0, 210436), '!': (234, 0, 2, 4, 8, 210436), '"': (296, 0, 2, 5, 8, 210468), '#': (352, 0, 2, 6, 8, 210508), '$': (352, 0, 1, 6, 10, 210556), '%': (586, 0, 2, 9, 8, 210616), '&': (548, 0, 2, 9, 8, 210688), "'": (151, 0, 2, 3, 8, 210760), '(': (234, 0, 2, 5, 10, 210784), ')': (234, -1, 2, 5, 10, 210834), '*': (352, 0, 2, 6, 8, 210884), '+': (475, 0, 3, 7, 7, 210932), ',': (176, 0, 9, 3, 3, 210981), '-': (234, 0, 7, 4, 3, 210990), '.': (176, 0, 9, 3, 1, 211002), '/': (196, -1, 2, 5, 8, 211005), '0': (352, 0, 2, 6, 8, 211045), '1': (352, 0, 2, 6, 8, 211093), '2': (352, 0, 2, 6, 8, 211141), '3': (352, -1, 2, 7, 8, 211189), '4': (352, 0, 2, 6, 8, 211245), '5': (352, 0, 2, 6, 8, 211293), '6': (352, 0, 2, 6, 8, 211341), '7': (352, 0, 2, 6, 8, 211389), '8': (352, 0, 2, 6, 8, 211437), '9': (352, 0, 2, 6, 8, 211485), ':': (234, 0, 5, 4, 5, 211533), ';': (234, 0, 5, 4, 7, 211553), '<': (475, 0, 3, 7, 7, 211581), '=': (475, 0, 5, 7, 5, 211630), '>': (475, 0, 3, 7, 7, 211665), '?': (352, 0, 2, 6, 8, 211714), '@': (648, 0, 2, 10, 10, 211762), 'A': (430, -1, 2, 8, 8, 211862), 'B': (430, 0, 2, 7, 8, 211926), 'C': (470, 0, 2, 8, 8, 211982), 'D': (508, -1, 2, 9, 9, 212046), 'E': (430, -1, 2, 8, 8, 212127), 'F': (430, -1, 2, 8, 8, 212191), 'G': (508, 0, 2, 8, 8, 212255), 'H': (508, -1, 2, 10, 8, 212319), 'I': (234, -1, 2, 6, 8, 212399), 'J': (312, 0, 2, 6, 8, 212447), 'K': (470, -1, 2, 9, 8, 212495), 'L': (392, -1, 2, 7, 8, 212567), 'M': (586, -1, 2, 11, 8, 212623), 'N': (470, -1, 2, 9, 8, 212711), 'O': (508, 0, 2, 8, 8, 212783), 'P': (430, -1, 2, 8, 8, 212847), 'Q': (508, 0, 2, 8, 10, 212911), 'R': (430, -1, 2, 8, 8, 212991), 'S': (352, 0, 2, 6, 8, 213055), 'T': (392, 0, 2, 7, 8, 213103), 'U': (508, 0, 2, 9, 8, 213159), 'V': (430, 0, 2, 8, 8, 213231), 'W': (586, 0, 2, 10, 8, 213295), 'X': (430, -1, 2, 9, 8, 213375), 'Y': (392, 0, 2, 8, 8, 213447), 'Z': (392, 0, 2, 7, 8, 213511), '[': (274, 0, 2, 5, 9, 213567), '\\': (196, 0, 2, 3, 8, 213612), ']': (274, -1, 2, 5, 9, 213636), '^': (297, 0, 2, 6, 8, 213681), '_': (352, -1, 10, 7, 2, 213729), '`': (234, 0, 2, 4, 8, 213743), 'a': (352, 0, 5, 6, 5, 213775), 'b': (352, 0, 2, 6, 8, 213805), 'c': (312, 0, 5, 5, 5, 213853), 'd': (352, 0, 2, 6, 8, 213878), 'e': (312, 0, 5, 5, 5, 213926), 'f': (196, 0, 2, 5, 10, 213951), 'g': (352, 0, 5, 6, 7, 214001), 'h': (352, 0, 2, 6, 8, 214043), 'i': (196, 0, 2, 3, 8, 214091), 'j': (196, -2, 2, 5, 10, 214115), 'k': (312, 0, 2, 6, 8, 214165), 'l': (196, 0, 2, 3, 8, 214213), 'm': (508, 0, 5, 8, 5, 214237), 'n': (352, 0, 5, 6, 5, 214277), 'o': (352, 0, 5, 6, 5, 214307), 'p': (352, -1, 5, 7, 7, 214337), 'q': (352, 0, 5, 6, 7, 214386), 'r': (274, 0, 5, 5, 5, 214428), 's': (274, 0, 5, 4, 5, 214453), 't': (196, 0, 4, 4, 6, 214473), 'u': (352, 0, 5, 6, 5, 214497), 'v': (312, 0, 5, 5, 5, 214527), 'w': (470, 0, 5, 8, 5, 214552), 'x': (312, -1, 5, 6, 5, 214592), 'y': (312, -1, 5, 6, 7, 214622), 'z': (274, -1, 5, 6, 5, 214664), '{': (282, 0, 2, 5, 9, 214694), '|': (194, 0, 2, 3, 10, 214739), '}': (282, 0, 2, 5, 9, 214769), '~': (381, 0, 5, 6, 5, 214814), '£': (352, 0, 2, 6, 8, 214844), '°': (282, 0, 2, 5, 8, 214892), '·': (176, 0, 6, 3, 4, 214932), 'à': (352, 0, 2, 6, 8, 214944), 'á': (352, 0, 2, 6, 8, 214992), 'ç': (312, 0, 5, 5, 7, 215040), 'é': (312, 0, 2, 6, 8, 215075), 'í': (196, 0, 2, 4, 8, 215123), 'ñ': (352, 0, 2, 6, 8, 215155), 'ü': (352, 0, 1, 6, 9, 215203), '–': (352, -1, 7, 7, 3, 215257), '—': (626, -1, 7, 11, 3, 215278), '‘': (234, 0, 2, 4, 8, 215311), '’': (234, 0, 2, 4, 8, 215343), '“': (392, 0, 2, 6, 8, 215375), '”': (392, 0, 2, 6, 8, 215423), '•': (246, 0, 5, 4, 5, 215471), '…': (626, 0, 9, 10, 1, 215491), '€': (352, 0, 2, 6, 8, 215501), '−': (475, 0, 6, 7, 4, 215549), '▲': (697, 0, 4, 11, 6, 215577)}, 'k': {' A': -13, 'A ': -13, 'L ': -13, 'P ': -13, 'T ': -13, 'V ': -13, 're': -26, '’ ': -78}}, 'strip': {'g': {' ': (213, 0, 11, 3, 0, 215643), '!': (256, 0, 2, 4, 9, 215643), '"': (364, 0, 2, 6, 9, 215679), '#': (427, 0, 2, 7, 9, 215733), '$': (427, 0, 1, 7, 12, 215796), '%': (683, 0, 2, 11, 9, 215880), '&': (555, 0, 2, 9, 9, 215979), "'": (183, 0, 2, 3, 9, 216060), '(': (256, 0, 2, 4, 11, 216087), ')': (256, 0, 2, 4, 11, 216131), '*': (299, 0, 2, 5, 9, 216175), '+': (449, 0, 3, 7, 8, 216220), ',': (213, 0, 9, 3, 4, 216276), '-': (256, 0, 7, 4, 4, 216288), '.': (213, 0, 9, 3, 2, 216304), '/': (213, 0, 2, 4, 9, 216310), '0': (427, 0, 2, 7, 9, 216346), '1': (427, 0, 2, 7, 9, 216409), '2': (427, 0, 2, 7, 9, 216472), '3': (427, 0, 2, 7, 9, 216535), '4': (427, 0, 2, 7, 9, 216598), '5': (427, 0, 2, 7, 9, 216661), '6': (427, 0, 2, 7, 9, 216724), '7': (427, 0, 2, 7, 9, 216787), '8': (427, 0, 2, 7, 9, 216850), '9': (427, 0, 2, 7, 9, 216913), ':': (256, 0, 4, 4, 7, 216976), ';': (256, 0, 4, 4, 9, 217004), '<': (449, 0, 4, 7, 7, 217040), '=': (449, 0, 5, 7, 6, 217089), '>': (449, 0, 4, 7, 7, 217131), '?': (469, 0, 2, 7, 9, 217180), '@': (749, 0, 2, 12, 11, 217243), 'A': (555, 0, 2, 9, 9, 217375), 'B': (555, 0, 2, 9, 9, 217456), 'C': (555, 0, 2, 9, 9, 217537), 'D': (555, 0, 2, 9, 9, 217618), 'E': (512, 0, 2, 8, 9, 217699), 'F': (469, 0, 2, 7, 9, 217771), 'G': (597, 0, 2, 9, 9, 217834), 'H': (555, 0, 2, 9, 9, 217915), 'I': (213, 0, 2, 3, 9, 217996), 'J': (427, 0, 2, 7, 9, 218023), 'K': (555, 0, 2, 9, 9, 218086), 'L': (469, 0, 2, 7, 9, 218167), 'M': (640, 0, 2, 10, 9, 218230), 'N': (555, 0, 2, 9, 9, 218320), 'O': (597, 0, 2, 9, 9, 218401), 'P': (512, 0, 2, 8, 9, 218482), 'Q': (597, 0, 2, 9, 11, 218554), 'R': (555, 0, 2, 9, 9, 218653), 'S': (512, 0, 2, 8, 9, 218734), 'T': (469, 0, 2, 8, 9, 218806), 'U': (555, 0, 2, 9, 9, 218878), 'V': (512, 0, 2, 8, 9, 218959), 'W': (725, 0, 2, 12, 9, 219031), 'X': (512, 0, 2, 8, 9, 219139), 'Y': (512, 0, 2, 8, 9, 219211), 'Z': (469, 0, 2, 7, 9, 219283), '[': (256, 0, 2, 4, 11, 219346), '\\': (213, 0, 2, 4, 9, 219390), ']': (256, 0, 2, 4, 11, 219426), '^': (449, 0, 2, 7, 9, 219470), '_': (427, -1, 11, 8, 2, 219533), '`': (256, 0, 0, 4, 11, 219549), 'a': (427, 0, 4, 7, 7, 219593), 'b': (469, 0, 2, 7, 9, 219642), 'c': (427, 0, 4, 7, 7, 219705), 'd': (469, 0, 2, 7, 9, 219754), 'e': (427, 0, 4, 7, 7, 219817), 'f': (256, 0, 2, 5, 9, 219866), 'g': (469, 0, 4, 7, 9, 219911), 'h': (469, 0, 2, 7, 9, 219974), 'i': (213, 0, 2, 3, 9, 220037), 'j': (213, -1, 2, 4, 11, 220064), 'k': (427, 0, 2, 7, 9, 220108), 'l': (213, 0, 2, 3, 9, 220171), 'm': (683, 0, 4, 11, 7, 220198), 'n': (469, 0, 4, 7, 7, 220275), 'o': (469, 0, 4, 7, 7, 220324), 'p': (469, 0, 4, 7, 9, 220373), 'q': (469, 0, 4, 7, 9, 220436), 'r': (299, 0, 4, 5, 7, 220499), 's': (427, 0, 4, 7, 7, 220534), 't': (256, 0, 3, 4, 8, 220583), 'u': (469, 0, 4, 7, 7, 220615), 'v': (427, 0, 4, 7, 7, 220664), 'w': (597, -1, 4, 11, 7, 220713), 'x': (427, 0, 4, 7, 7, 220790), 'y': (427, 0, 4, 7, 9, 220839), 'z': (384, 0, 4, 6, 7, 220902), '{': (299, 0, 2, 5, 11, 220944), '|': (215, 0, 2, 3, 12, 220999), '}': (299, 0, 2, 5, 11, 221035), '~': (449, 0, 6, 7, 5, 221090), '£': (427, 0, 2, 7, 9, 221125), '°': (307, 0, 2, 5, 9, 221188), '·': (256, 0, 6, 4, 5, 221233), 'à': (427, 0, 0, 7, 11, 221253), 'á': (427, 0, 0, 7, 11, 221330), 'ç': (427, 0, 4, 7, 9, 221407), 'é': (427, 0, 0, 7, 11, 221470), 'í': (213, 0, 0, 4, 11, 221547), 'ñ': (469, 0, 1, 7, 10, 221591), 'ü': (469, 0, 2, 7, 9, 221661), '–': (427, 0, 7, 7, 4, 221724), '—': (768, 0, 7, 12, 4, 221752), '‘': (213, 0, 2, 3, 9, 221800), '’': (213, 0, 2, 3, 9, 221827), '“': (384, 0, 2, 6, 9, 221854), '”': (384, 0, 2, 6, 9, 221908), '•': (269, 0, 6, 4, 5, 221962), '…': (768, 0, 9, 12, 2, 221982), '€': (427, 0, 2, 7, 9, 222006), '−': (449, 0, 6, 7, 5, 222069), '▲': (760, 0, 4, 12, 7, 222104)}, 'k': {' A': -28, ' Y': -14, 'A ': -28, 'AT': -57, 'L ': -14, 'P ': -14, 'Y ': -14, '’ ': -42}}, 'foot': {'g': {' ': (178, 0, 10, 3, 0, 222188), '!': (178, 0, 3, 3, 7, 222188), '"': (227, 0, 3, 4, 7, 222209), '#': (356, 0, 3, 6, 7, 222237), '$': (356, 0, 2, 6, 9, 222279), '%': (569, 0, 3, 9, 7, 222333), '&': (427, 0, 3, 7, 7, 222396), "'": (122, 0, 3, 2, 7, 222445), '(': (213, 0, 3, 4, 9, 222459), ')': (213, 0, 3, 3, 9, 222495), '*': (249, 0, 3, 4, 7, 222522), '+': (374, 0, 3, 6, 7, 222550), ',': (178, 0, 9, 3, 2, 222592), '-': (213, 0, 7, 3, 3, 222598), '.': (178, 0, 9, 3, 1, 222607), '/': (178, 0, 3, 3, 7, 222610), '0': (356, 0, 3, 6, 7, 222631), '1': (356, 0, 3, 6, 7, 222673), '2': (356, 0, 3, 6, 7, 222715), '3': (356, 0, 3, 6, 7, 222757), '4': (356, 0, 3, 6, 7, 222799), '5': (356, 0, 3, 6, 7, 222841), '6': (356, 0, 3, 6, 7, 222883), '7': (356, 0, 3, 6, 7, 222925), '8': (356, 0, 3, 6, 7, 222967), '9': (356, 0, 3, 6, 7, 223009), ':': (178, 0, 5, 3, 5, 223051), ';': (178, 0, 5, 3, 6, 223066), '<': (374, 0, 4, 6, 6, 223084), '=': (374, 0, 5, 6, 5, 223120), '>': (374, 0, 4, 6, 6, 223150), '?': (356, 0, 3, 6, 7, 223186), '@': (650, 0, 3, 10, 8, 223228), 'A': (427, 0, 3, 7, 7, 223308), 'B': (427, 0, 3, 7, 7, 223357), 'C': (462, 0, 3, 7, 7, 223406), 'D': (462, 0, 3, 7, 7, 223455), 'E': (427, 0, 3, 7, 7, 223504), 'F': (391, 0, 3, 6, 7, 223553), 'G': (498, 0, 3, 8, 7, 223595), 'H': (462, 0, 3, 7, 7, 223651), 'I': (178, 0, 3, 3, 7, 223700), 'J': (320, 0, 3, 5, 7, 223721), 'K': (427, 0, 3, 7, 7, 223756), 'L': (356, 0, 3, 6, 7, 223805), 'M': (533, 0, 3, 8, 7, 223847), 'N': (462, 0, 3, 7, 7, 223903), 'O': (498, 0, 3, 8, 7, 223952), 'P': (427, 0, 3, 7, 7, 224008), 'Q': (498, 0, 3, 8, 9, 224057), 'R': (462, 0, 3, 7, 7, 224129), 'S': (427, 0, 3, 7, 7, 224178), 'T': (391, 0, 3, 6, 7, 224227), 'U': (462, 0, 3, 7, 7, 224269), 'V': (427, 0, 3, 7, 7, 224318), 'W': (604, 0, 3, 10, 7, 224367), 'X': (427, 0, 3, 7, 7, 224437), 'Y': (427, 0, 3, 7, 7, 224486), 'Z': (391, 0, 3, 6, 7, 224535), '[': (178, 0, 3, 3, 9, 224577), '\\': (178, 0, 3, 3, 7, 224604), ']': (178, 0, 3, 3, 9, 224625), '^': (300, 0, 3, 5, 7, 224652), '_': (356, -1, 10, 7, 2, 224687), '`': (213, 0, 2, 3, 8, 224701), 'a': (356, 0, 5, 6, 5, 224725), 'b': (356, 0, 3, 6, 7, 224755), 'c': (320, 0, 5, 5, 5, 224797), 'd': (356, 0, 3, 6, 7, 224822), 'e': (356, 0, 5, 6, 5, 224864), 'f': (178, 0, 3, 3, 7, 224894), 'g': (356, 0, 5, 6, 7, 224915), 'h': (356, 0, 3, 6, 7, 224957), 'i': (142, 0, 3, 2, 7, 224999), 'j': (142, -1, 3, 3, 9, 225013), 'k': (320, 0, 3, 6, 7, 225040), 'l': (142, 0, 3, 2, 7, 225082), 'm': (533, 0, 5, 8, 5, 225096), 'n': (356, 0, 5, 6, 5, 225136), 'o': (356, 0, 5, 6, 5, 225166), 'p': (356, 0, 5, 6, 7, 225196), 'q': (356, 0, 5, 6, 7, 225238), 'r': (213, 0, 5, 4, 5, 225280), 's': (320, 0, 5, 5, 5, 225300), 't': (178, 0, 4, 3, 6, 225325), 'u': (356, 0, 5, 6, 5, 225343), 'v': (320, 0, 5, 5, 5, 225373), 'w': (462, -1, 5, 9, 5, 225398), 'x': (320, 0, 5, 5, 5, 225443), 'y': (320, 0, 5, 5, 7, 225468), 'z': (320, 0, 5, 5, 5, 225503), '{': (214, 0, 3, 4, 9, 225528), '|': (166, 0, 3, 3, 9, 225564), '}': (214, 0, 3, 4, 9, 225591), '~': (374, 0, 5, 6, 5, 225627), '£': (356, 0, 3, 6, 7, 225657), '°': (256, 0, 3, 4, 7, 225699), '·': (213, 0, 6, 3, 4, 225727), 'à': (356, 0, 2, 6, 8, 225739), 'á': (356, 0, 2, 6, 8, 225787), 'ç': (320, 0, 5, 5, 7, 225835), 'é': (356, 0, 2, 6, 8, 225870), 'í': (178, 0, 2, 3, 8, 225918), 'ñ': (356, 0, 2, 6, 8, 225942), 'ü': (356, 0, 3, 6, 7, 225990), '–': (356, 0, 7, 6, 3, 226032), '—': (640, 0, 7, 10, 3, 226050), '‘': (142, 0, 3, 2, 7, 226080), '’': (142, 0, 3, 2, 7, 226094), '“': (213, 0, 3, 3, 7, 226108), '”': (213, 0, 3, 3, 7, 226129), '•': (224, 0, 5, 4, 5, 226150), '…': (640, 0, 9, 10, 1, 226170), '€': (356, 0, 3, 6, 7, 226180), '−': (374, 0, 6, 6, 4, 226222), '▲': (633, 0, 4, 10, 6, 226246)}, 'k': {' A': -35, ' T': -12, ' Y': -12, 'A ': -35, 'AT': -47, 'L ': -24, 'LY': -47, 'P ': -12, 'P,': -82, 'PA': -47, 'T ': -12, 'Ti': -24, 'Y ': -12, 'Yo': -59, 'y,': -47, '’ ': -24}}, 'thermo': {'g': {' ': (267, 0, 14, 4, 0, 226306), '!': (320, 0, 3, 5, 11, 226306), '"': (455, 0, 3, 7, 11, 226361), '#': (534, 0, 3, 9, 11, 226438), '$': (534, 0, 2, 9, 14, 226537), '%': (854, 0, 3, 13, 11, 226663), '&': (693, 0, 3, 11, 11, 226806), "'": (228, 0, 3, 4, 11, 226927), '(': (320, 0, 3, 5, 14, 226971), ')': (320, 0, 3, 5, 14, 227041), '*': (374, 0, 3, 6, 11, 227111), '+': (561, 0, 5, 9, 9, 227177), ',': (267, 0, 12, 4, 4, 227258), '-': (320, 0, 9, 5, 5, 227274), '.': (267, 0, 12, 4, 2, 227299), '/': (267, 0, 3, 5, 11, 227307), '0': (534, 0, 3, 8, 11, 227362), '1': (534, 0, 3, 8, 11, 227450), '2': (534, 0, 3, 8, 11, 227538), '3': (534, 0, 3, 8, 11, 227626), '4': (534, 0, 3, 9, 11, 227714), '5': (534, 0, 3, 8, 11, 227813), '6': (534, 0, 3, 8, 11, 227901), '7': (534, 0, 3, 8, 11, 227989), '8': (534, 0, 3, 8, 11, 228077), '9': (534, 0, 3, 8, 11, 228165), ':': (320, 0, 6, 5, 8, 228253), ';': (320, 0, 6, 5, 10, 228293), '<': (561, 0, 5, 9, 9, 228343), '=': (561, 0, 7, 9, 7, 228424), '>': (561, 0, 5, 9, 9, 228487), '?': (586, 0, 3, 9, 11, 228568), '@': (936, 0, 3, 15, 13, 228667), 'A': (693, 0, 3, 11, 11, 228862), 'B': (693, 0, 3, 11, 11, 228983), 'C': (693, 0, 3, 11, 11, 229104), 'D': (693, 0, 3, 11, 11, 229225), 'E': (640, 0, 3, 10, 11, 229346), 'F': (586, 0, 3, 9, 11, 229456), 'G': (747, 0, 3, 12, 11, 229555), 'H': (693, 0, 3, 11, 11, 229687), 'I': (267, 0, 3, 4, 11, 229808), 'J': (534, 0, 3, 8, 11, 229852), 'K': (693, 0, 3, 11, 11, 229940), 'L': (586, 0, 3, 9, 11, 230061), 'M': (800, 0, 3, 13, 11, 230160), 'N': (693, 0, 3, 11, 11, 230303), 'O': (747, 0, 3, 12, 11, 230424), 'P': (640, 0, 3, 10, 11, 230556), 'Q': (747, 0, 3, 12, 14, 230666), 'R': (693, 0, 3, 11, 11, 230834), 'S': (640, 0, 3, 10, 11, 230955), 'T': (586, 0, 3, 9, 11, 231065), 'U': (693, 0, 3, 11, 11, 231164), 'V': (640, 0, 3, 10, 11, 231285), 'W': (906, 0, 3, 15, 11, 231395), 'X': (640, 0, 3, 10, 11, 231560), 'Y': (640, 0, 3, 10, 11, 231670), 'Z': (586, 0, 3, 9, 11, 231780), '[': (320, 0, 3, 5, 14, 231879), '\\': (267, 0, 3, 5, 11, 231949), ']': (320, 0, 3, 5, 14, 232004), '^': (561, 0, 3, 9, 11, 232074), '_': (534, -1, 14, 10, 2, 232173), '`': (320, 0, 2, 5, 12, 232193), 'a': (534, 0, 6, 9, 8, 232253), 'b': (586, 0, 3, 9, 11, 232325), 'c': (534, 0, 6, 8, 8, 232424), 'd': (586, 0, 3, 9, 11, 232488), 'e': (534, 0, 6, 8, 8, 232587), 'f': (320, 0, 3, 6, 11, 232651), 'g': (586, 0, 6, 9, 11, 232717), 'h': (586, 0, 3, 9, 11, 232816), 'i': (267, 0, 3, 4, 11, 232915), 'j': (267, -1, 3, 5, 14, 232959), 'k': (534, 0, 3, 9, 11, 233029), 'l': (267, 0, 3, 4, 11, 233128), 'm': (854, 0, 6, 13, 8, 233172), 'n': (586, 0, 6, 9, 8, 233276), 'o': (586, 0, 6, 9, 8, 233348), 'p': (586, 0, 6, 9, 11, 233420), 'q': (586, 0, 6, 9, 11, 233519), 'r': (374, 0, 6, 6, 8, 233618), 's': (534, 0, 6, 8, 8, 233666), 't': (320, 0, 4, 5, 10, 233730), 'u': (586, 0, 6, 9, 8, 233780), 'v': (534, 0, 6, 9, 8, 233852), 'w': (747, -1, 6, 13, 8, 233924), 'x': (534, 0, 6, 9, 8, 234028), 'y': (534, 0, 6, 9, 11, 234100), 'z': (480, 0, 6, 8, 8, 234199), '{': (374, 0, 3, 6, 14, 234263), '|': (269, 0, 3, 4, 14, 234347), '}': (374, 0, 3, 6, 14, 234403), '~': (561, 0, 7, 9, 7, 234487), '£': (534, 0, 3, 9, 11, 234550), '°': (384, 0, 3, 6, 11, 234649), '·': (320, 0, 7, 5, 7, 234715), 'à': (534, 0, 2, 9, 12, 234750), 'á': (534, 0, 2, 9, 12, 234858), 'ç': (534, 0, 6, 8, 11, 234966), 'é': (534, 0, 2, 8, 12, 235054), 'í': (267, 0, 2, 5, 12, 235150), 'ñ': (586, 0, 2, 9, 12, 235210), 'ü': (586, 0, 3, 9, 11, 235318), '–': (534, 0, 9, 8, 5, 235417), '—': (960, 0, 9, 15, 5, 235457), '‘': (267, 0, 3, 4, 11, 235532), '’': (267, 0, 3, 4, 11, 235576), '“': (480, 0, 3, 8, 11, 235620), '”': (480, 0, 3, 8, 11, 235708), '•': (336, 0, 7, 5, 7, 235796), '…': (960, 0, 12, 15, 2, 235831), '€': (534, 0, 3, 9, 11, 235861), '−': (561, 0, 8, 9, 6, 235960), '▲': (950, 0, 5, 15, 9, 236014)}, 'k': {' A': -36, ' Y': -17, 'A ': -36, 'L ': -17, 'P ': -17, 'Y ': -17, '’ ': -53}}, 'head13': {'g': {' ': (208, 0, 12, 3, 0, 236149), '!': (277, 0, 3, 4, 9, 236149), '"': (462, 0, 3, 7, 9, 236185), '#': (416, 0, 3, 7, 9, 236248), '$': (416, 0, 2, 7, 11, 236311), '%': (832, 0, 3, 13, 9, 236388), '&': (693, 0, 3, 11, 9, 236505), "'": (231, 0, 3, 4, 9, 236604), '(': (277, 0, 3, 4, 12, 236640), ')': (277, 0, 3, 4, 12, 236688), '*': (416, 0, 3, 7, 9, 236736), '+': (474, 0, 5, 7, 7, 236799), ',': (208, 0, 10, 3, 4, 236848), '-': (277, 0, 8, 4, 4, 236860), '.': (208, 0, 10, 3, 2, 236876), '/': (231, -1, 3, 5, 9, 236882), '0': (416, 0, 3, 7, 9, 236927), '1': (416, 0, 3, 7, 9, 236990), '2': (416, 0, 3, 7, 9, 237053), '3': (416, 0, 3, 7, 9, 237116), '4': (416, 0, 3, 7, 9, 237179), '5': (416, 0, 3, 7, 9, 237242), '6': (416, 0, 3, 7, 9, 237305), '7': (416, 0, 3, 7, 9, 237368), '8': (416, 0, 3, 7, 9, 237431), '9': (416, 0, 3, 7, 9, 237494), ':': (277, 0, 6, 4, 6, 237557), ';': (277, 0, 6, 4, 8, 237581), '<': (474, 0, 4, 7, 8, 237613), '=': (474, 0, 6, 7, 6, 237669), '>': (474, 0, 4, 7, 8, 237711), '?': (416, 0, 3, 7, 9, 237767), '@': (774, 0, 3, 12, 11, 237830), 'A': (601, 0, 3, 10, 9, 237962), 'B': (555, 0, 3, 9, 10, 238052), 'C': (601, 0, 3, 9, 9, 238142), 'D': (601, 0, 3, 9, 10, 238223), 'E': (555, 0, 3, 9, 9, 238313), 'F': (508, 0, 3, 8, 9, 238394), 'G': (647, 0, 3, 10, 9, 238466), 'H': (647, 0, 3, 10, 9, 238556), 'I': (324, 0, 3, 5, 9, 238646), 'J': (416, 0, 3, 7, 9, 238691), 'K': (647, 0, 3, 11, 9, 238754), 'L': (555, 0, 3, 9, 9, 238853), 'M': (785, 0, 3, 12, 9, 238934), 'N': (601, 0, 3, 10, 9, 239042), 'O': (647, 0, 3, 10, 9, 239132), 'P': (508, 0, 3, 8, 9, 239222), 'Q': (647, 0, 3, 10, 11, 239294), 'R': (601, 0, 3, 10, 9, 239404), 'S': (463, 0, 3, 7, 9, 239494), 'T': (555, 0, 3, 9, 9, 239557), 'U': (601, 0, 3, 10, 9, 239638), 'V': (601, 0, 3, 10, 9, 239728), 'W': (832, 0, 3, 13, 9, 239818), 'X': (601, 0, 3, 10, 9, 239935), 'Y': (601, 0, 3, 10, 9, 240025), 'Z': (555, 0, 3, 9, 9, 240115), '[': (277, 0, 3, 4, 11, 240196), '\\': (231, -1, 3, 5, 9, 240240), ']': (277, 0, 3, 4, 11, 240285), '^': (483, 0, 3, 8, 9, 240329), '_': (416, -1, 12, 8, 2, 240401), '`': (277, 0, 3, 4, 9, 240417), 'a': (416, 0, 6, 7, 6, 240453), 'b': (463, 0, 3, 7, 9, 240495), 'c': (369, 0, 6, 6, 6, 240558), 'd': (463, 0, 3, 8, 9, 240594), 'e': (369, 0, 6, 6, 6, 240666), 'f': (277, 0, 3, 5, 9, 240702), 'g': (416, 0, 5, 7, 10, 240747), 'h': (463, 0, 3, 8, 9, 240817), 'i': (231, 0, 3, 4, 9, 240889), 'j': (277, -1, 3, 5, 12, 240925), 'k': (463, 0, 3, 8, 9, 240985), 'l': (231, 0, 3, 4, 9, 241057), 'm': (693, 0, 6, 11, 6, 241093), 'n': (463, 0, 6, 8, 6, 241159), 'o': (416, 0, 6, 7, 6, 241207), 'p': (463, 0, 6, 7, 9, 241249), 'q': (463, 0, 5, 8, 10, 241312), 'r': (369, 0, 6, 6, 6, 241392), 's': (324, 0, 6, 5, 6, 241428), 't': (277, 0, 5, 5, 7, 241458), 'u': (463, 0, 6, 7, 6, 241493), 'v': (416, 0, 6, 7, 6, 241535), 'w': (601, 0, 6, 10, 6, 241577), 'x': (416, 0, 6, 7, 6, 241637), 'y': (416, 0, 6, 7, 9, 241679), 'z': (369, 0, 6, 6, 6, 241742), '{': (328, 0, 3, 5, 11, 241778), '|': (183, 0, 3, 3, 12, 241833), '}': (328, 0, 3, 5, 11, 241869), '~': (433, 0, 6, 7, 6, 241924), '£': (416, 0, 3, 7, 9, 241966), '°': (333, 0, 3, 5, 9, 242029), '·': (277, 0, 7, 4, 5, 242074), 'à': (416, 0, 3, 7, 9, 242094), 'á': (416, 0, 3, 7, 9, 242157), 'ç': (369, 0, 6, 6, 9, 242220), 'é': (369, 0, 3, 6, 9, 242274), 'í': (231, 0, 3, 4, 9, 242328), 'ñ': (463, 0, 3, 8, 9, 242364), 'ü': (463, 0, 3, 7, 9, 242436), '–': (416, -1, 9, 8, 3, 242499), '—': (832, -1, 9, 15, 3, 242523), '‘': (277, 0, 3, 4, 9, 242568), '’': (277, 0, 3, 4, 9, 242604), '“': (416, 0, 3, 7, 9, 242640), '”': (416, 0, 3, 7, 9, 242703), '•': (291, 0, 6, 5, 6, 242766), '…': (832, 0, 10, 13, 2, 242796), '€': (416, 0, 3, 7, 9, 242822), '−': (474, 0, 7, 7, 5, 242885), '▲': (823, 0, 4, 13, 8, 242920)}, 'k': {' A': -46, ' T': -15, ' V': -15, ' W': -15, ' Y': -31, '11': -46, 'A ': -46, 'F ': -31, 'L ': -46, 'P ': -46, 'T ': -15, 'Ta': -76, 'To': -76, 'Tr': -62, 'Tu': -76, 'V ': -15, 'Vo': -76, 'W ': -15, 'Wa': -46, 'Y ': -31, 'r ': -15, 'rc': -15, 're': -15, 'ro': -15, 'v.': -46, '’ ': -62}}, 'head12': {'g': {' ': (192, 0, 11, 3, 0, 243024), '!': (256, 0, 2, 4, 9, 243024), '"': (426, 0, 2, 7, 9, 243060), '#': (384, 0, 2, 6, 9, 243123), '$': (384, 0, 1, 6, 11, 243177), '%': (768, 0, 2, 12, 9, 243243), '&': (640, 0, 2, 10, 9, 243351), "'": (213, 0, 2, 3, 9, 243441), '(': (256, 0, 2, 4, 12, 243468), ')': (256, 0, 2, 4, 12, 243516), '*': (384, 0, 2, 6, 9, 243564), '+': (438, 0, 4, 7, 7, 243618), ',': (192, 0, 9, 3, 4, 243667), '-': (256, 0, 8, 4, 3, 243679), '.': (192, 0, 9, 3, 2, 243691), '/': (213, -1, 2, 5, 9, 243697), '0': (384, 0, 2, 6, 9, 243742), '1': (384, 0, 2, 6, 9, 243796), '2': (384, 0, 2, 6, 9, 243850), '3': (384, 0, 2, 6, 9, 243904), '4': (384, 0, 2, 6, 9, 243958), '5': (384, 0, 2, 6, 9, 244012), '6': (384, 0, 2, 6, 9, 244066), '7': (384, 0, 2, 6, 9, 244120), '8': (384, 0, 2, 6, 9, 244174), '9': (384, 0, 2, 6, 9, 244228), ':': (256, 0, 5, 4, 6, 244282), ';': (256, 0, 5, 4, 8, 244306), '<': (438, 0, 3, 7, 8, 244338), '=': (438, 0, 5, 7, 6, 244394), '>': (438, 0, 3, 7, 8, 244436), '?': (384, 0, 2, 6, 9, 244492), '@': (714, 0, 2, 11, 11, 244546), 'A': (555, 0, 2, 9, 9, 244667), 'B': (512, 0, 2, 8, 10, 244748), 'C': (555, 0, 2, 9, 9, 244828), 'D': (555, 0, 2, 9, 10, 244909), 'E': (512, 0, 2, 8, 9, 244999), 'F': (469, 0, 2, 7, 9, 245071), 'G': (597, 0, 2, 9, 9, 245134), 'H': (597, 0, 2, 10, 9, 245215), 'I': (299, 0, 2, 5, 9, 245305), 'J': (384, 0, 2, 6, 9, 245350), 'K': (597, 0, 2, 10, 9, 245404), 'L': (512, 0, 2, 8, 9, 245494), 'M': (725, 0, 2, 11, 9, 245566), 'N': (555, 0, 2, 9, 9, 245665), 'O': (597, 0, 2, 9, 9, 245746), 'P': (469, 0, 2, 7, 9, 245827), 'Q': (597, 0, 2, 9, 11, 245890), 'R': (555, 0, 2, 9, 9, 245989), 'S': (427, 0, 2, 7, 9, 246070), 'T': (512, 0, 2, 8, 9, 246133), 'U': (555, 0, 2, 9, 9, 246205), 'V': (555, 0, 2, 9, 9, 246286), 'W': (768, 0, 2, 12, 9, 246367), 'X': (555, 0, 2, 9, 9, 246475), 'Y': (555, 0, 2, 9, 9, 246556), 'Z': (512, 0, 2, 8, 9, 246637), '[': (256, 0, 2, 4, 11, 246709), '\\': (213, -1, 2, 5, 9, 246753), ']': (256, 0, 2, 4, 11, 246798), '^': (446, 0, 2, 7, 9, 246842), '_': (384, -1, 11, 8, 2, 246905), '`': (256, 0, 2, 4, 9, 246921), 'a': (384, 0, 5, 6, 6, 246957), 'b': (427, 0, 2, 7, 9, 246993), 'c': (341, 0, 5, 6, 6, 247056), 'd': (427, 0, 2, 7, 9, 247092), 'e': (341, 0, 5, 6, 6, 247155), 'f': (256, 0, 2, 5, 9, 247191), 'g': (384, 0, 4, 6, 10, 247236), 'h': (427, 0, 2, 7, 9, 247296), 'i': (213, 0, 2, 4, 9, 247359), 'j': (256, -1, 2, 5, 12, 247395), 'k': (427, 0, 2, 7, 9, 247455), 'l': (213, 0, 2, 4, 9, 247518), 'm': (640, 0, 5, 10, 6, 247554), 'n': (427, 0, 5, 7, 6, 247614), 'o': (384, 0, 5, 6, 6, 247656), 'p': (427, 0, 5, 7, 9, 247692), 'q': (427, 0, 4, 7, 10, 247755), 'r': (341, 0, 5, 6, 6, 247825), 's': (299, 0, 5, 5, 6, 247861), 't': (256, 0, 4, 4, 7, 247891), 'u': (427, 0, 5, 7, 6, 247919), 'v': (384, 0, 5, 6, 6, 247961), 'w': (555, 0, 5, 9, 6, 247997), 'x': (384, 0, 5, 6, 6, 248051), 'y': (384, 0, 5, 6, 9, 248087), 'z': (341, 0, 5, 6, 6, 248141), '{': (303, 0, 2, 5, 11, 248177), '|': (169, 0, 2, 3, 12, 248232), '}': (303, 0, 2, 5, 11, 248268), '~': (399, 0, 6, 7, 5, 248323), '£': (384, 0, 2, 6, 9, 248358), '°': (307, 0, 2, 5, 9, 248412), '·': (256, 0, 6, 4, 5, 248457), 'à': (384, 0, 2, 6, 9, 248477), 'á': (384, 0, 2, 6, 9, 248531), 'ç': (341, 0, 5, 6, 9, 248585), 'é': (341, 0, 2, 6, 9, 248639), 'í': (213, 0, 2, 4, 9, 248693), 'ñ': (427, 0, 2, 7, 9, 248729), 'ü': (427, 0, 2, 7, 9, 248792), '–': (384, -1, 8, 8, 3, 248855), '—': (768, -1, 8, 14, 3, 248879), '‘': (256, 0, 2, 4, 9, 248921), '’': (256, 0, 2, 4, 9, 248957), '“': (384, 0, 2, 6, 9, 248993), '”': (384, 0, 2, 6, 9, 249047), '•': (269, 0, 5, 4, 6, 249101), '…': (768, 0, 9, 12, 2, 249125), '€': (384, 0, 2, 6, 9, 249149), '−': (438, 0, 6, 7, 5, 249203), '▲': (760, 0, 4, 12, 7, 249238)}, 'k': {' A': -42, ' T': -14, ' V': -14, ' W': -14, ' Y': -28, '11': -42, 'A ': -42, 'F ': -28, 'L ': -42, 'P ': -42, 'T ': -14, 'Ta': -70, 'To': -70, 'Tr': -57, 'Tu': -70, 'V ': -14, 'Vo': -70, 'W ': -14, 'Wa': -42, 'Y ': -28, 'r ': -14, 'rc': -14, 're': -14, 'ro': -14, 'v.': -42, '’ ': -57}}, 'head11': {'g': {' ': (176, 0, 10, 3, 0, 249322), '!': (234, 0, 2, 4, 8, 249322), '"': (391, 0, 2, 6, 8, 249354), '#': (352, 0, 2, 6, 8, 249402), '$': (352, 0, 1, 6, 10, 249450), '%': (704, 0, 2, 11, 8, 249510), '&': (586, 0, 2, 9, 8, 249598), "'": (196, 0, 2, 3, 8, 249670), '(': (234, 0, 2, 4, 10, 249694), ')': (234, 0, 2, 4, 10, 249734), '*': (352, 0, 2, 6, 8, 249774), '+': (401, 0, 4, 6, 6, 249822), ',': (176, 0, 8, 3, 4, 249858), '-': (234, 0, 7, 4, 3, 249870), '.': (176, 0, 8, 3, 2, 249882), '/': (196, -1, 2, 5, 8, 249888), '0': (352, 0, 2, 6, 8, 249928), '1': (352, 0, 2, 6, 8, 249976), '2': (352, 0, 2, 6, 8, 250024), '3': (352, 0, 2, 6, 8, 250072), '4': (352, 0, 2, 6, 8, 250120), '5': (352, 0, 2, 6, 8, 250168), '6': (352, 0, 2, 6, 8, 250216), '7': (352, 0, 2, 6, 8, 250264), '8': (352, 0, 2, 6, 8, 250312), '9': (352, 0, 2, 6, 8, 250360), ':': (234, 0, 5, 4, 5, 250408), ';': (234, 0, 5, 4, 7, 250428), '<': (401, 0, 4, 6, 6, 250456), '=': (401, 0, 5, 6, 5, 250492), '>': (401, 0, 4, 6, 6, 250522), '?': (352, 0, 2, 6, 8, 250558), '@': (655, 0, 2, 10, 10, 250606), 'A': (508, 0, 2, 8, 8, 250706), 'B': (470, 0, 2, 8, 9, 250770), 'C': (508, 0, 2, 8, 8, 250842), 'D': (508, 0, 2, 8, 9, 250906), 'E': (470, 0, 2, 7, 8, 250978), 'F': (430, 0, 2, 7, 8, 251034), 'G': (548, 0, 2, 9, 8, 251090), 'H': (548, 0, 2, 9, 8, 251162), 'I': (274, 0, 2, 4, 8, 251234), 'J': (352, 0, 2, 6, 8, 251266), 'K': (548, 0, 2, 9, 8, 251314), 'L': (470, 0, 2, 7, 8, 251386), 'M': (664, 0, 2, 11, 8, 251442), 'N': (508, 0, 2, 8, 8, 251530), 'O': (548, 0, 2, 9, 8, 251594), 'P': (430, 0, 2, 7, 8, 251666), 'Q': (548, 0, 2, 9, 10, 251722), 'R': (508, 0, 2, 9, 8, 251812), 'S': (392, 0, 2, 6, 8, 251884), 'T': (470, 0, 2, 8, 8, 251932), 'U': (508, 0, 2, 8, 8, 251996), 'V': (508, 0, 2, 8, 8, 252060), 'W': (704, 0, 2, 11, 8, 252124), 'X': (508, 0, 2, 8, 8, 252212), 'Y': (508, 0, 2, 8, 8, 252276), 'Z': (470, 0, 2, 7, 8, 252340), '[': (234, 0, 2, 4, 9, 252396), '\\': (196, -1, 2, 5, 8, 252432), ']': (234, 0, 2, 4, 9, 252472), '^': (409, 0, 2, 6, 8, 252508), '_': (352, -1, 10, 7, 2, 252556), '`': (234, 0, 2, 4, 8, 252570), 'a': (352, 0, 5, 6, 5, 252602), 'b': (392, 0, 2, 6, 8, 252632), 'c': (312, 0, 5, 5, 5, 252680), 'd': (392, 0, 2, 6, 8, 252705), 'e': (312, 0, 5, 5, 5, 252753), 'f': (234, 0, 2, 4, 8, 252778), 'g': (352, 0, 4, 6, 8, 252810), 'h': (392, 0, 2, 6, 8, 252858), 'i': (196, 0, 2, 3, 8, 252906), 'j': (234, -1, 2, 5, 10, 252930), 'k': (392, 0, 2, 7, 8, 252980), 'l': (196, 0, 2, 3, 8, 253036), 'm': (586, 0, 5, 9, 5, 253060), 'n': (392, 0, 5, 6, 5, 253105), 'o': (352, 0, 5, 6, 5, 253135), 'p': (392, 0, 5, 6, 7, 253165), 'q': (392, 0, 4, 7, 8, 253207), 'r': (312, 0, 5, 5, 5, 253263), 's': (274, 0, 5, 5, 5, 253288), 't': (234, 0, 4, 4, 6, 253313), 'u': (392, 0, 5, 6, 5, 253337), 'v': (352, 0, 5, 6, 5, 253367), 'w': (508, 0, 5, 8, 5, 253397), 'x': (352, 0, 5, 6, 5, 253437), 'y': (352, 0, 5, 6, 7, 253467), 'z': (312, 0, 5, 5, 5, 253509), '{': (277, 0, 2, 4, 9, 253534), '|': (155, 0, 2, 2, 10, 253570), '}': (277, 0, 2, 4, 9, 253590), '~': (366, 0, 5, 6, 5, 253626), '£': (352, 0, 2, 6, 8, 253656), '°': (282, 0, 2, 4, 8, 253704), '·': (235, 0, 5, 4, 5, 253736), 'à': (352, 0, 2, 6, 8, 253756), 'á': (352, 0, 2, 6, 8, 253804), 'ç': (312, 0, 5, 5, 7, 253852), 'é': (312, 0, 2, 5, 8, 253887), 'í': (196, 0, 2, 4, 8, 253927), 'ñ': (392, 0, 2, 6, 8, 253959), 'ü': (392, 0, 2, 6, 8, 254007), '–': (352, -1, 7, 7, 3, 254055), '—': (704, -1, 7, 13, 3, 254076), '‘': (234, 0, 2, 4, 8, 254115), '’': (234, 0, 2, 4, 8, 254147), '“': (352, 0, 2, 6, 8, 254179), '”': (352, 0, 2, 6, 8, 254227), '•': (246, 0, 5, 4, 5, 254275), '…': (704, 0, 8, 11, 2, 254295), '€': (352, 0, 2, 6, 8, 254317), '−': (401, 0, 6, 6, 4, 254365), '▲': (697, 0, 4, 11, 6, 254389)}, 'k': {' A': -39, ' T': -13, ' V': -13, ' W': -13, ' Y': -26, '11': -39, 'A ': -39, 'F ': -26, 'L ': -39, 'P ': -39, 'T ': -13, 'Ta': -65, 'To': -65, 'Tr': -52, 'Tu': -65, 'V ': -13, 'Vo': -65, 'W ': -13, 'Wa': -39, 'Y ': -26, 'r ': -13, 'rc': -13, 're': -13, 'ro': -13, 'v.': -39, '’ ': -52}}, 'sum10': {'g': {' ': (160, 0, 9, 3, 0, 254455), '!': (213, 0, 2, 3, 7, 254455), '"': (261, 0, 2, 4, 7, 254476), '#': (320, 0, 2, 5, 7, 254504), '$': (320, 0, 1, 5, 9, 254539), '%': (533, 0, 2, 8, 7, 254584), '&': (498, 0, 2, 8, 7, 254640), "'": (115, 0, 2, 2, 7, 254696), '(': (213, 0, 2, 4, 9, 254710), ')': (213, 0, 2, 3, 9, 254746), '*': (320, 0, 2, 5, 7, 254773), '+': (361, 0, 2, 6, 7, 254808), ',': (160, 0, 8, 3, 3, 254850), '-': (213, 0, 6, 3, 3, 254859), '.': (160, 0, 8, 3, 1, 254868), '/': (178, 0, 2, 3, 7, 254871), '0': (320, 0, 2, 5, 7, 254892), '1': (320, 0, 2, 5, 7, 254927), '2': (320, 0, 2, 5, 7, 254962), '3': (320, 0, 2, 5, 7, 254997), '4': (320, 0, 2, 5, 7, 255032), '5': (320, 0, 2, 5, 7, 255067), '6': (320, 0, 2, 5, 7, 255102), '7': (320, 0, 2, 5, 7, 255137), '8': (320, 0, 2, 5, 7, 255172), '9': (320, 0, 2, 5, 7, 255207), ':': (178, 0, 4, 3, 5, 255242), ';': (178, 0, 4, 3, 7, 255257), '<': (361, 0, 3, 6, 6, 255278), '=': (361, 0, 4, 6, 5, 255314), '>': (361, 0, 3, 6, 6, 255344), '?': (284, 0, 2, 5, 7, 255380), '@': (589, 0, 2, 9, 9, 255415), 'A': (462, 0, 2, 8, 7, 255496), 'B': (427, 0, 2, 7, 7, 255552), 'C': (427, 0, 2, 7, 7, 255601), 'D': (462, 0, 2, 7, 7, 255650), 'E': (391, 0, 2, 6, 7, 255699), 'F': (356, 0, 2, 6, 7, 255741), 'G': (462, 0, 2, 7, 7, 255783), 'H': (462, 0, 2, 7, 7, 255832), 'I': (213, 0, 2, 3, 7, 255881), 'J': (249, 0, 2, 4, 7, 255902), 'K': (462, 0, 2, 8, 7, 255930), 'L': (391, 0, 2, 6, 7, 255986), 'M': (569, 0, 2, 9, 7, 256028), 'N': (462, 0, 2, 7, 7, 256091), 'O': (462, 0, 2, 7, 7, 256140), 'P': (356, 0, 2, 6, 7, 256189), 'Q': (462, 0, 2, 8, 9, 256231), 'R': (427, 0, 2, 7, 7, 256303), 'S': (356, 0, 2, 6, 7, 256352), 'T': (391, 0, 2, 6, 7, 256394), 'U': (462, 0, 2, 8, 7, 256436), 'V': (462, 0, 2, 8, 7, 256492), 'W': (604, 0, 2, 10, 7, 256548), 'X': (462, 0, 2, 8, 7, 256618), 'Y': (462, 0, 2, 7, 7, 256674), 'Z': (391, 0, 2, 6, 7, 256723), '[': (213, 0, 2, 3, 8, 256765), '\\': (178, 0, 2, 3, 7, 256789), ']': (213, 0, 2, 3, 8, 256810), '^': (300, 0, 2, 5, 7, 256834), '_': (320, -1, 9, 7, 2, 256869), '`': (213, 0, 1, 3, 8, 256883), 'a': (284, 0, 4, 5, 5, 256907), 'b': (320, 0, 2, 5, 7, 256932), 'c': (284, 0, 4, 5, 5, 256967), 'd': (320, 0, 2, 5, 7, 256992), 'e': (284, 0, 4, 5, 5, 257027), 'f': (213, 0, 2, 4, 7, 257052), 'g': (320, 0, 3, 5, 8, 257080), 'h': (320, 0, 2, 5, 7, 257120), 'i': (178, 0, 1, 3, 8, 257155), 'j': (178, -1, 1, 4, 10, 257179), 'k': (320, 0, 2, 5, 7, 257219), 'l': (178, 0, 2, 3, 7, 257254), 'm': (498, 0, 4, 8, 5, 257275), 'n': (320, 0, 4, 5, 5, 257315), 'o': (320, 0, 4, 5, 5, 257340), 'p': (320, 0, 4, 5, 7, 257365), 'q': (320, 0, 3, 5, 8, 257400), 'r': (213, 0, 4, 4, 5, 257440), 's': (249, 0, 4, 4, 5, 257460), 't': (178, 0, 2, 3, 7, 257480), 'u': (320, 0, 4, 5, 5, 257501), 'v': (320, 0, 4, 5, 5, 257526), 'w': (462, 0, 4, 8, 5, 257551), 'x': (320, 0, 4, 5, 5, 257591), 'y': (320, 0, 4, 5, 7, 257616), 'z': (284, 0, 4, 5, 5, 257651), '{': (307, 0, 2, 5, 8, 257676), '|': (128, 0, 2, 2, 9, 257716), '}': (307, 0, 2, 5, 8, 257734), '~': (346, 0, 5, 6, 4, 257774), '£': (320, 0, 2, 5, 7, 257798), '°': (256, 0, 2, 4, 7, 257833), '·': (213, 0, 5, 3, 4, 257861), 'à': (284, 0, 1, 5, 8, 257873), 'á': (284, 0, 1, 5, 8, 257913), 'ç': (284, 0, 4, 5, 7, 257953), 'é': (284, 0, 1, 5, 8, 257988), 'í': (178, 0, 1, 3, 8, 258028), 'ñ': (320, 0, 1, 5, 8, 258052), 'ü': (320, 0, 2, 5, 7, 258092), '–': (320, -1, 6, 7, 3, 258127), '—': (640, -1, 6, 12, 3, 258148), '‘': (213, 0, 2, 3, 7, 258184), '’': (213, 0, 2, 3, 7, 258205), '“': (284, 0, 2, 5, 7, 258226), '”': (284, 0, 2, 4, 7, 258261), '•': (224, 0, 4, 4, 5, 258289), '…': (640, 0, 8, 10, 1, 258309), '€': (320, 0, 2, 5, 7, 258319), '−': (361, 0, 5, 6, 4, 258354), '▲': (633, 0, 3, 10, 6, 258378)}, 'k': {' A': -35, ' T': -12, ' V': -12, ' W': -12, ' Y': -24, '11': -24, 'A ': -35, 'L ': -24, 'P ': -24, 'T ': -12, 'Ta': -45, 'Te': -45, 'To': -45, 'Tr': -22, 'Tu': -22, 'Tw': -45, 'V ': -12, 'W ': -12, 'Wi': -26, 'Wo': -51, 'Y ': -24, 'Ya': -64, 'r.': -35, 'rg': -12, 'v,': -42, 'w.': -42, 'y,': -42, 'y.': -42, '’ ': -47}}, 'sum9': {'g': {' ': (144, 0, 9, 2, 0, 258438), '!': (192, 0, 2, 3, 7, 258438), '"': (235, 0, 2, 4, 7, 258459), '#': (288, 0, 2, 5, 7, 258487), '$': (288, 0, 1, 5, 9, 258522), '%': (480, 0, 2, 8, 7, 258567), '&': (448, 0, 2, 7, 7, 258623), "'": (104, 0, 2, 2, 7, 258672), '(': (192, 0, 2, 3, 9, 258686), ')': (192, 0, 2, 3, 9, 258713), '*': (288, 0, 2, 5, 7, 258740), '+': (325, 0, 3, 5, 6, 258775), ',': (144, 0, 8, 2, 3, 258805), '-': (192, 0, 6, 3, 3, 258811), '.': (144, 0, 8, 2, 1, 258820), '/': (160, 0, 2, 3, 7, 258822), '0': (288, 0, 2, 5, 7, 258843), '1': (288, 0, 2, 5, 7, 258878), '2': (288, 0, 2, 5, 7, 258913), '3': (288, 0, 2, 5, 7, 258948), '4': (288, 0, 2, 5, 7, 258983), '5': (288, 0, 2, 5, 7, 259018), '6': (288, 0, 2, 5, 7, 259053), '7': (288, 0, 2, 5, 7, 259088), '8': (288, 0, 2, 5, 7, 259123), '9': (288, 0, 2, 5, 7, 259158), ':': (160, 0, 4, 3, 5, 259193), ';': (160, 0, 4, 3, 7, 259208), '<': (325, 0, 3, 5, 6, 259229), '=': (325, 0, 4, 5, 5, 259259), '>': (325, 0, 3, 5, 6, 259284), '?': (256, 0, 2, 4, 7, 259314), '@': (530, 0, 2, 8, 9, 259342), 'A': (416, 0, 2, 7, 7, 259414), 'B': (384, 0, 2, 6, 7, 259463), 'C': (384, 0, 2, 6, 7, 259505), 'D': (416, 0, 2, 7, 7, 259547), 'E': (352, 0, 2, 6, 7, 259596), 'F': (320, 0, 2, 5, 7, 259638), 'G': (416, 0, 2, 7, 7, 259673), 'H': (416, 0, 2, 7, 7, 259722), 'I': (192, 0, 2, 3, 7, 259771), 'J': (224, 0, 2, 4, 7, 259792), 'K': (416, 0, 2, 7, 7, 259820), 'L': (352, 0, 2, 6, 7, 259869), 'M': (512, 0, 2, 8, 7, 259911), 'N': (416, 0, 2, 7, 7, 259967), 'O': (416, 0, 2, 7, 7, 260016), 'P': (320, 0, 2, 5, 7, 260065), 'Q': (416, 0, 2, 7, 9, 260100), 'R': (384, 0, 2, 6, 7, 260163), 'S': (320, 0, 2, 5, 7, 260205), 'T': (352, 0, 2, 6, 7, 260240), 'U': (416, 0, 2, 7, 7, 260282), 'V': (416, 0, 2, 7, 7, 260331), 'W': (544, 0, 2, 9, 7, 260380), 'X': (416, 0, 2, 7, 7, 260443), 'Y': (416, 0, 2, 7, 7, 260492), 'Z': (352, 0, 2, 6, 7, 260541), '[': (192, 0, 2, 3, 8, 260583), '\\': (160, 0, 2, 3, 7, 260607), ']': (192, 0, 2, 3, 8, 260628), '^': (270, 0, 2, 5, 7, 260652), '_': (288, -1, 9, 6, 2, 260687), '`': (192, 0, 1, 3, 8, 260699), 'a': (256, 0, 4, 4, 5, 260723), 'b': (288, 0, 2, 5, 7, 260743), 'c': (256, 0, 4, 4, 5, 260778), 'd': (288, 0, 2, 5, 7, 260798), 'e': (256, 0, 4, 4, 5, 260833), 'f': (192, 0, 2, 3, 7, 260853), 'g': (288, 0, 3, 5, 8, 260874), 'h': (288, 0, 2, 5, 7, 260914), 'i': (160, 0, 2, 3, 7, 260949), 'j': (160, -1, 2, 4, 9, 260970), 'k': (288, 0, 2, 5, 7, 261006), 'l': (160, 0, 2, 3, 7, 261041), 'm': (448, 0, 4, 7, 5, 261062), 'n': (288, 0, 4, 5, 5, 261097), 'o': (288, 0, 4, 5, 5, 261122), 'p': (288, 0, 4, 5, 7, 261147), 'q': (288, 0, 3, 5, 8, 261182), 'r': (192, 0, 4, 3, 5, 261222), 's': (224, 0, 4, 4, 5, 261237), 't': (160, 0, 3, 3, 6, 261257), 'u': (288, 0, 4, 5, 5, 261275), 'v': (288, 0, 4, 5, 5, 261300), 'w': (416, 0, 4, 7, 5, 261325), 'x': (288, 0, 4, 5, 5, 261360), 'y': (288, 0, 4, 5, 7, 261385), 'z': (256, 0, 4, 4, 5, 261420), '{': (276, 0, 2, 4, 8, 261440), '|': (115, 0, 2, 2, 9, 261472), '}': (276, 0, 2, 4, 8, 261490), '~': (312, 0, 5, 5, 4, 261522), '£': (288, 0, 2, 5, 7, 261542), '°': (230, 0, 2, 4, 7, 261577), '·': (192, 0, 5, 3, 4, 261605), 'à': (256, 0, 1, 4, 8, 261617), 'á': (256, 0, 1, 4, 8, 261649), 'ç': (256, 0, 4, 4, 7, 261681), 'é': (256, 0, 1, 4, 8, 261709), 'í': (160, 0, 1, 3, 8, 261741), 'ñ': (288, 0, 1, 5, 8, 261765), 'ü': (288, 0, 2, 5, 7, 261805), '–': (288, -1, 6, 6, 3, 261840), '—': (576, -1, 6, 11, 3, 261858), '‘': (192, 0, 2, 3, 7, 261891), '’': (192, 0, 2, 3, 7, 261912), '“': (256, 0, 2, 4, 7, 261933), '”': (256, 0, 2, 4, 7, 261961), '•': (202, 0, 5, 3, 4, 261989), '…': (576, 0, 8, 9, 1, 262001), '€': (288, 0, 2, 5, 7, 262010), '−': (325, 0, 5, 5, 4, 262045), '▲': (570, 0, 4, 9, 5, 262065)}, 'k': {' A': -32, ' T': -10, ' V': -10, ' W': -10, ' Y': -21, '11': -21, 'A ': -32, 'L ': -21, 'P ': -21, 'T ': -10, 'Ta': -40, 'Te': -40, 'To': -40, 'Tr': -20, 'Tu': -20, 'Tw': -40, 'V ': -10, 'W ': -10, 'Wi': -23, 'Wo': -46, 'Y ': -21, 'Ya': -58, 'r.': -32, 'rg': -10, 'v,': -37, 'w.': -37, 'y,': -37, 'y.': -37, '’ ': -43}}, 'brief11': {'g': {' ': (176, 0, 10, 3, 0, 262110), '!': (234, 0, 2, 4, 8, 262110), '"': (287, 0, 2, 4, 8, 262142), '#': (352, 0, 2, 6, 8, 262174), '$': (352, 0, 1, 6, 10, 262222), '%': (586, 0, 2, 9, 8, 262282), '&': (548, 0, 2, 9, 8, 262354), "'": (127, 0, 2, 2, 8, 262426), '(': (234, 0, 2, 4, 10, 262442), ')': (234, 0, 2, 4, 10, 262482), '*': (352, 0, 2, 6, 8, 262522), '+': (397, 0, 3, 6, 7, 262570), ',': (176, 0, 9, 3, 3, 262612), '-': (234, 0, 7, 4, 3, 262621), '.': (176, 0, 9, 3, 1, 262633), '/': (196, 0, 2, 4, 8, 262636), '0': (352, 0, 2, 6, 8, 262668), '1': (352, 0, 2, 6, 8, 262716), '2': (352, 0, 2, 6, 8, 262764), '3': (352, 0, 2, 6, 8, 262812), '4': (352, 0, 2, 6, 8, 262860), '5': (352, 0, 2, 6, 8, 262908), '6': (352, 0, 2, 6, 8, 262956), '7': (352, 0, 2, 6, 8, 263004), '8': (352, 0, 2, 6, 8, 263052), '9': (352, 0, 2, 6, 8, 263100), ':': (196, 0, 5, 3, 5, 263148), ';': (196, 0, 5, 3, 7, 263163), '<': (397, 0, 4, 6, 6, 263184), '=': (397, 0, 5, 6, 5, 263220), '>': (397, 0, 4, 6, 6, 263250), '?': (312, 0, 2, 5, 8, 263286), '@': (648, 0, 2, 10, 10, 263326), 'A': (508, 0, 2, 8, 8, 263426), 'B': (470, 0, 2, 7, 8, 263490), 'C': (470, 0, 2, 7, 8, 263546), 'D': (508, 0, 2, 8, 8, 263602), 'E': (430, 0, 2, 7, 8, 263666), 'F': (392, 0, 2, 6, 8, 263722), 'G': (508, 0, 2, 8, 8, 263770), 'H': (508, 0, 2, 8, 8, 263834), 'I': (234, 0, 2, 4, 8, 263898), 'J': (274, 0, 2, 5, 8, 263930), 'K': (508, 0, 2, 8, 8, 263970), 'L': (430, 0, 2, 7, 8, 264034), 'M': (626, 0, 2, 10, 8, 264090), 'N': (508, 0, 2, 8, 8, 264170), 'O': (508, 0, 2, 8, 8, 264234), 'P': (392, 0, 2, 6, 8, 264298), 'Q': (508, 0, 2, 8, 10, 264346), 'R': (470, 0, 2, 8, 8, 264426), 'S': (392, 0, 2, 6, 8, 264490), 'T': (430, 0, 2, 7, 8, 264538), 'U': (508, 0, 2, 8, 8, 264594), 'V': (508, 0, 2, 8, 8, 264658), 'W': (664, 0, 2, 11, 8, 264722), 'X': (508, 0, 2, 8, 8, 264810), 'Y': (508, 0, 2, 8, 8, 264874), 'Z': (430, 0, 2, 7, 8, 264938), '[': (234, 0, 2, 4, 9, 264994), '\\': (196, 0, 2, 4, 8, 265030), ']': (234, 0, 2, 4, 9, 265062), '^': (330, 0, 2, 6, 8, 265098), '_': (352, -1, 10, 7, 2, 265146), '`': (234, 0, 2, 4, 8, 265160), 'a': (312, 0, 5, 5, 5, 265192), 'b': (352, 0, 2, 6, 8, 265217), 'c': (312, 0, 5, 5, 5, 265265), 'd': (352, 0, 2, 6, 8, 265290), 'e': (312, 0, 5, 5, 5, 265338), 'f': (234, 0, 2, 4, 8, 265363), 'g': (352, 0, 4, 6, 8, 265395), 'h': (352, 0, 2, 6, 8, 265443), 'i': (196, 0, 2, 3, 8, 265491), 'j': (196, -1, 2, 4, 10, 265515), 'k': (352, 0, 2, 6, 8, 265555), 'l': (196, 0, 2, 3, 8, 265603), 'm': (548, 0, 5, 9, 5, 265627), 'n': (352, 0, 5, 6, 5, 265672), 'o': (352, 0, 5, 6, 5, 265702), 'p': (352, 0, 5, 6, 7, 265732), 'q': (352, 0, 4, 6, 8, 265774), 'r': (234, 0, 5, 4, 5, 265822), 's': (274, 0, 5, 4, 5, 265842), 't': (196, 0, 3, 3, 7, 265862), 'u': (352, 0, 5, 6, 5, 265883), 'v': (352, 0, 5, 6, 5, 265913), 'w': (508, 0, 5, 8, 5, 265943), 'x': (352, 0, 5, 6, 5, 265983), 'y': (352, 0, 5, 6, 7, 266013), 'z': (312, 0, 5, 5, 5, 266055), '{': (338, 0, 2, 5, 9, 266080), '|': (141, 0, 2, 2, 10, 266125), '}': (338, 0, 2, 5, 9, 266145), '~': (381, 0, 5, 6, 5, 266190), '£': (352, 0, 2, 6, 8, 266220), '°': (282, 0, 2, 4, 8, 266268), '·': (234, 0, 6, 4, 4, 266300), 'à': (312, 0, 2, 5, 8, 266316), 'á': (312, 0, 2, 5, 8, 266356), 'ç': (312, 0, 5, 5, 8, 266396), 'é': (312, 0, 2, 5, 8, 266436), 'í': (196, 0, 2, 3, 8, 266476), 'ñ': (352, 0, 2, 6, 8, 266500), 'ü': (352, 0, 2, 6, 8, 266548), '–': (352, -1, 7, 7, 3, 266596), '—': (704, -1, 7, 13, 3, 266617), '‘': (234, 0, 2, 4, 8, 266656), '’': (234, 0, 2, 4, 8, 266688), '“': (312, 0, 2, 5, 8, 266720), '”': (312, 0, 2, 5, 8, 266760), '•': (246, 0, 5, 4, 5, 266800), '…': (704, 0, 9, 11, 1, 266820), '€': (352, 0, 2, 6, 8, 266831), '−': (397, 0, 6, 6, 4, 266879), '▲': (697, 0, 4, 11, 6, 266903)}, 'k': {' A': -39, ' T': -13, ' V': -13, ' W': -13, ' Y': -26, 'A ': -39, 'AT': -78, 'L ': -26, 'P ': -26, 'RT': -42, 'T ': -13, 'TA': -56, 'Te': -49, 'To': -49, 'V ': -13, 'Ve': -78, 'W ': -13, 'Wo': -56, 'Y ': -26, 'ff': -13, 'rg': -13, '’ ': -52}}, 'brief10': {'g': {' ': (160, 0, 9, 3, 0, 266969), '!': (213, 0, 2, 3, 7, 266969), '"': (261, 0, 2, 4, 7, 266990), '#': (320, 0, 2, 5, 7, 267018), '$': (320, 0, 1, 5, 9, 267053), '%': (533, 0, 2, 8, 7, 267098), '&': (498, 0, 2, 8, 7, 267154), "'": (115, 0, 2, 2, 7, 267210), '(': (213, 0, 2, 4, 9, 267224), ')': (213, 0, 2, 3, 9, 267260), '*': (320, 0, 2, 5, 7, 267287), '+': (361, 0, 2, 6, 7, 267322), ',': (160, 0, 8, 3, 3, 267364), '-': (213, 0, 6, 3, 3, 267373), '.': (160, 0, 8, 3, 1, 267382), '/': (178, 0, 2, 3, 7, 267385), '0': (320, 0, 2, 5, 7, 267406), '1': (320, 0, 2, 5, 7, 267441), '2': (320, 0, 2, 5, 7, 267476), '3': (320, 0, 2, 5, 7, 267511), '4': (320, 0, 2, 5, 7, 267546), '5': (320, 0, 2, 5, 7, 267581), '6': (320, 0, 2, 5, 7, 267616), '7': (320, 0, 2, 5, 7, 267651), '8': (320, 0, 2, 5, 7, 267686), '9': (320, 0, 2, 5, 7, 267721), ':': (178, 0, 4, 3, 5, 267756), ';': (178, 0, 4, 3, 7, 267771), '<': (361, 0, 3, 6, 6, 267792), '=': (361, 0, 4, 6, 5, 267828), '>': (361, 0, 3, 6, 6, 267858), '?': (284, 0, 2, 5, 7, 267894), '@': (589, 0, 2, 9, 9, 267929), 'A': (462, 0, 2, 8, 7, 268010), 'B': (427, 0, 2, 7, 7, 268066), 'C': (427, 0, 2, 7, 7, 268115), 'D': (462, 0, 2, 7, 7, 268164), 'E': (391, 0, 2, 6, 7, 268213), 'F': (356, 0, 2, 6, 7, 268255), 'G': (462, 0, 2, 7, 7, 268297), 'H': (462, 0, 2, 7, 7, 268346), 'I': (213, 0, 2, 3, 7, 268395), 'J': (249, 0, 2, 4, 7, 268416), 'K': (462, 0, 2, 8, 7, 268444), 'L': (391, 0, 2, 6, 7, 268500), 'M': (569, 0, 2, 9, 7, 268542), 'N': (462, 0, 2, 7, 7, 268605), 'O': (462, 0, 2, 7, 7, 268654), 'P': (356, 0, 2, 6, 7, 268703), 'Q': (462, 0, 2, 8, 9, 268745), 'R': (427, 0, 2, 7, 7, 268817), 'S': (356, 0, 2, 6, 7, 268866), 'T': (391, 0, 2, 6, 7, 268908), 'U': (462, 0, 2, 8, 7, 268950), 'V': (462, 0, 2, 8, 7, 269006), 'W': (604, 0, 2, 10, 7, 269062), 'X': (462, 0, 2, 8, 7, 269132), 'Y': (462, 0, 2, 7, 7, 269188), 'Z': (391, 0, 2, 6, 7, 269237), '[': (213, 0, 2, 3, 8, 269279), '\\': (178, 0, 2, 3, 7, 269303), ']': (213, 0, 2, 3, 8, 269324), '^': (300, 0, 2, 5, 7, 269348), '_': (320, -1, 9, 7, 2, 269383), '`': (213, 0, 1, 3, 8, 269397), 'a': (284, 0, 4, 5, 5, 269421), 'b': (320, 0, 2, 5, 7, 269446), 'c': (284, 0, 4, 5, 5, 269481), 'd': (320, 0, 2, 5, 7, 269506), 'e': (284, 0, 4, 5, 5, 269541), 'f': (213, 0, 2, 4, 7, 269566), 'g': (320, 0, 3, 5, 8, 269594), 'h': (320, 0, 2, 5, 7, 269634), 'i': (178, 0, 1, 3, 8, 269669), 'j': (178, -1, 1, 4, 10, 269693), 'k': (320, 0, 2, 5, 7, 269733), 'l': (178, 0, 2, 3, 7, 269768), 'm': (498, 0, 4, 8, 5, 269789), 'n': (320, 0, 4, 5, 5, 269829), 'o': (320, 0, 4, 5, 5, 269854), 'p': (320, 0, 4, 5, 7, 269879), 'q': (320, 0, 3, 5, 8, 269914), 'r': (213, 0, 4, 4, 5, 269954), 's': (249, 0, 4, 4, 5, 269974), 't': (178, 0, 2, 3, 7, 269994), 'u': (320, 0, 4, 5, 5, 270015), 'v': (320, 0, 4, 5, 5, 270040), 'w': (462, 0, 4, 8, 5, 270065), 'x': (320, 0, 4, 5, 5, 270105), 'y': (320, 0, 4, 5, 7, 270130), 'z': (284, 0, 4, 5, 5, 270165), '{': (307, 0, 2, 5, 8, 270190), '|': (128, 0, 2, 2, 9, 270230), '}': (307, 0, 2, 5, 8, 270248), '~': (346, 0, 5, 6, 4, 270288), '£': (320, 0, 2, 5, 7, 270312), '°': (256, 0, 2, 4, 7, 270347), '·': (213, 0, 5, 3, 4, 270375), 'à': (284, 0, 1, 5, 8, 270387), 'á': (284, 0, 1, 5, 8, 270427), 'ç': (284, 0, 4, 5, 7, 270467), 'é': (284, 0, 1, 5, 8, 270502), 'í': (178, 0, 1, 3, 8, 270542), 'ñ': (320, 0, 1, 5, 8, 270566), 'ü': (320, 0, 2, 5, 7, 270606), '–': (320, -1, 6, 7, 3, 270641), '—': (640, -1, 6, 12, 3, 270662), '‘': (213, 0, 2, 3, 7, 270698), '’': (213, 0, 2, 3, 7, 270719), '“': (284, 0, 2, 5, 7, 270740), '”': (284, 0, 2, 4, 7, 270775), '•': (224, 0, 4, 4, 5, 270803), '…': (640, 0, 8, 10, 1, 270823), '€': (320, 0, 2, 5, 7, 270833), '−': (361, 0, 5, 6, 4, 270868), '▲': (633, 0, 3, 10, 6, 270892)}, 'k': {' A': -35, ' T': -12, ' V': -12, ' W': -12, ' Y': -24, 'A ': -35, 'AT': -71, 'L ': -24, 'P ': -24, 'RT': -38, 'T ': -12, 'TA': -51, 'Te': -45, 'To': -45, 'V ': -12, 'Ve': -71, 'W ': -12, 'Wo': -51, 'Y ': -24, 'ff': -12, 'rg': -12, '’ ': -47}}}

# --------------------------------------------------------------------------
# Font engine: advances, kerning and glyph blitting from the atlas
# --------------------------------------------------------------------------
_BLOB = zlib.decompress(b85decode(ATLAS_B85))


class Font:
    """One embedded typeface at one size.

    glyphs: {char: (advance, offset_x, offset_y, width, height, blob_start)}
    with advance in 1/64 px and offsets from the text anchor (left of the
    advance, top of the ascender). kern: {"AB": kern} in 1/64 px.
    """

    __slots__ = ("glyphs", "kern")

    def __init__(self, glyphs, kern):
        self.glyphs = glyphs
        self.kern = kern

    def length(self, text):
        """Advance width of `text` in px, kerning included."""
        total = 0
        prev = None
        glyphs = self.glyphs
        kern = self.kern
        for ch in text:
            if prev is not None:
                total += kern.get(prev + ch, 0)
            total += glyphs[ch][0]
            prev = ch
        return total / 64.0


FONTS = {key: Font(tab["g"], tab["k"]) for key, tab in FONT_TABLE.items()}


# --------------------------------------------------------------------------
# Raster canvas
# --------------------------------------------------------------------------
class Canvas:
    """A minimal RGB raster: rects, lines, ellipses, polygons, glyphs."""

    __slots__ = ("w", "h", "px")

    def __init__(self, w, h, color):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(color) * (w * h))

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def fill_rect(self, x0, y0, x1, y1, color):
        """Filled rectangle, both corners inclusive."""
        x0 = int(x0)
        y0 = int(y0)
        x1 = int(x1)
        y1 = int(y1)
        if x1 < x0 or y1 < y0:
            return
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w - 1, x1)
        y1 = min(self.h - 1, y1)
        if x1 < x0 or y1 < y0:
            return
        row = bytes(color) * (x1 - x0 + 1)
        off = (y0 * self.w + x0) * 3
        stride = self.w * 3
        px = self.px
        for _ in range(y0, y1 + 1):
            px[off:off + len(row)] = row
            off += stride

    def line(self, x0, y0, x1, y1, color, width=1):
        x0 = int(x0)
        y0 = int(y0)
        x1 = int(x1)
        y1 = int(y1)
        if y0 == y1:  # horizontal: thickens downward
            if x1 < x0:
                x0, x1 = x1, x0
            self.fill_rect(x0, y0, x1, y0 + width - 1, color)
            return
        if x0 == x1:  # vertical: thickens rightward
            if y1 < y0:
                y0, y1 = y1, y0
            self.fill_rect(x0, y0, x0 + width - 1, y1, color)
            return
        # general Bresenham with a square stamp (not used by this page,
        # kept so the primitive is complete)
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        offs = range(-(width // 2), width - width // 2)
        while True:
            for ox in offs:
                for oy in offs:
                    self.set(x0 + ox, y0 + oy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fill_ellipse(self, x0, y0, x1, y1, color):
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        rx = (x1 - x0) / 2.0
        ry = (y1 - y0) / 2.0
        if rx <= 0 or ry <= 0:
            return
        for yy in range(int(y0), int(y1) + 1):
            t = (yy - cy) / ry
            if t < -1.0 or t > 1.0:
                continue
            hw = rx * math.sqrt(1.0 - t * t)
            xa = int(math.ceil(cx - hw - 1e-9))
            xb = int(math.floor(cx + hw + 1e-9))
            self.fill_rect(xa, yy, xb, yy, color)

    def outline_ellipse(self, cx, cy, rx, ry, color, width=1):
        steps = max(72, int(6.3 * max(rx, ry)) + 8)
        offs = range(-(width // 2), width - width // 2)
        last = None
        for i in range(steps + 1):
            t = 2.0 * math.pi * i / steps
            px = int(round(cx + rx * math.cos(t)))
            py = int(round(cy + ry * math.sin(t)))
            if (px, py) == last:
                continue
            last = (px, py)
            for ox in offs:
                for oy in offs:
                    self.set(px + ox, py + oy, color)

    def fill_polygon(self, pts, color, clip_circle=None):
        """Scanline polygon fill; optionally clipped to a circle
        (cx, cy, r) — used to keep the globe's continents inside it."""
        ys = [p[1] for p in pts]
        ylo = max(0, min(ys))
        yhi = min(self.h - 1, max(ys))
        n = len(pts)
        for yy in range(ylo, yhi + 1):
            xs = []
            for i in range(n):
                xa, ya = pts[i]
                xb, yb = pts[(i + 1) % n]
                if (ya <= yy < yb) or (yb <= yy < ya):
                    xs.append(xa + (yy - ya) * (xb - xa) / (yb - ya))
            if len(xs) < 2:
                continue
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(round(xs[i]))
                xb = int(round(xs[i + 1]))
                if clip_circle is not None:
                    ccx, ccy, cr = clip_circle
                    rem = cr * cr - (yy - ccy) * (yy - ccy)
                    if rem < 0:
                        continue
                    hw = int(math.sqrt(rem))
                    xa = max(xa, ccx - hw)
                    xb = min(xb, ccx + hw)
                self.fill_rect(xa, yy, xb, yy, color)

    def rounded_rect(self, x0, y0, x1, y1, r, color):
        x0 = int(x0)
        y0 = int(y0)
        x1 = int(x1)
        y1 = int(y1)
        for yy in range(y0, y1 + 1):
            t = min(yy - y0, y1 - yy)
            if t < r:
                dx = r - int(round(math.sqrt(max(0, r * r - (r - t) * (r - t)))))
            else:
                dx = 0
            self.fill_rect(x0 + dx, yy, x1 - dx, yy, color)

    def rect_outline(self, x0, y0, x1, y1, color, width=2):
        self.fill_rect(x0, y0, x1, y0 + width - 1, color)
        self.fill_rect(x0, y1 - width + 1, x1, y1, color)
        self.fill_rect(x0, y0, x0 + width - 1, y1, color)
        self.fill_rect(x1 - width + 1, y0, x1, y1, color)

    def blit(self, off, w, h, x, y, color):
        """Alpha-blend one glyph mask from the atlas over the canvas."""
        px = self.px
        width = self.w
        height = self.h
        r, g, b = color
        blob = _BLOB
        for row in range(h):
            yy = y + row
            if yy < 0 or yy >= height:
                continue
            src = off + row * w
            base = (yy * width + x) * 3
            for col in range(w):
                a = blob[src + col]
                if not a:
                    continue
                xx = x + col
                if xx < 0 or xx >= width:
                    continue
                di = base + col * 3
                if a == 255:
                    px[di] = r
                    px[di + 1] = g
                    px[di + 2] = b
                else:
                    ia = 255 - a
                    px[di] = (r * a + px[di] * ia) // 255
                    px[di + 1] = (g * a + px[di + 1] * ia) // 255
                    px[di + 2] = (b * a + px[di + 2] * ia) // 255


def draw_text(cv, x, y, text, font, color):
    """Draw `text` with the anchor at (x, y): left of the advance,
    top of the ascender — the same anchor the measurements came from."""
    pen = 0  # 1/64 px, relative to x
    prev = None
    bx = int(x)
    by = int(y)
    glyphs = font.glyphs
    kern = font.kern
    for ch in text:
        if prev is not None:
            pen += kern.get(prev + ch, 0)
        g = glyphs[ch]
        if g[3] and g[4]:
            cv.blit(g[5], g[3], g[4], bx + (pen >> 6) + g[1], by + g[2], color)
        pen += g[0]
        prev = ch


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
def wrap(text, font, width):
    """Greedy word wrap; returns list of lines that fit `width` px."""
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if font.length(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, x, y, text, font, lh, width, fill=INK, max_lines=None):
    lines = wrap(text, font, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.length(last + "\u2026") > width:
            last = last[:-1]
        lines[-1] = last + "\u2026"
    for ln in lines:
        draw_text(cv, x, y, ln, font, fill)
        y += lh
    return y


# --------------------------------------------------------------------------
# Hero visual: a drawn globe with a fever thermometer (abstract, code-drawn)
# --------------------------------------------------------------------------
def draw_globe(cv, cx, cy, r):
    cv.fill_ellipse(cx - r, cy - r, cx + r, cy + r, GLOBE_SEA)
    # abstract continents, clipped to the globe's circle
    s = (2 * r + 2) / 164.0  # scale the sketch (drawn for r=81) to this radius

    def P(pts):
        return [(int(a * s) + cx - r - 1, int(b * s) + cy - r - 1) for a, b in pts]

    land = [
        [(30, 30), (85, 18), (105, 45), (80, 70), (45, 66), (26, 50)],
        [(72, 78), (98, 76), (100, 112), (82, 128), (70, 104)],
        [(112, 34), (150, 26), (168, 48), (150, 66), (118, 60)],
        [(124, 68), (146, 66), (148, 96), (128, 104), (118, 84)],
        [(152, 96), (178, 94), (182, 116), (160, 122)],
    ]
    for poly in land:
        cv.fill_polygon(P(poly), GLOBE_LAND, clip_circle=(cx, cy, r))
    for frac in (0.45, 0.8):
        w2 = int(r * frac)
        cv.outline_ellipse(cx, cy, w2, r, INK, 1)
    cv.line(cx, cy - r, cx, cy + r, INK, 1)
    for frac in (-0.55, 0.0, 0.55):
        yy = cy + int(r * frac)
        hw = int(r * (1 - frac * frac) ** 0.5)
        cv.line(cx - hw, yy, cx + hw, yy, INK, 1)
    cv.outline_ellipse(cx, cy, r, r, INK, 3)


def draw_thermometer(cv, x, y, h):
    wdt = 13
    cv.rounded_rect(x, y, x + wdt, y + h, 6, INK)
    cv.rounded_rect(x + 2, y + 2, x + wdt - 2, y + h - 2, 4, WHITE)
    bulb_r = 13
    bcx, bcy = x + wdt // 2, y + h + bulb_r - 2
    cv.fill_ellipse(bcx - bulb_r, bcy - bulb_r, bcx + bulb_r, bcy + bulb_r, INK)
    cv.fill_ellipse(bcx - bulb_r + 2, bcy - bulb_r + 2,
                    bcx + bulb_r - 2, bcy + bulb_r - 2, ACCENT)
    fill_h = int(h * 0.82)
    cv.rounded_rect(x + 3, y + h - fill_h, x + wdt - 3, y + h, 4, ACCENT)
    for i in range(5):
        ty = y + 8 + i * (h - 16) // 4
        cv.line(x + wdt + 3, ty, x + wdt + 10, ty, INK, 1)
    draw_text(cv, x - 8, y - 23, "+1.8\u00b0C", FONTS["thermo"], ACCENT)


# --------------------------------------------------------------------------
# Column layout with deterministic auto-fit
# --------------------------------------------------------------------------
# (headline px, headline lh, summary px, summary lh, item gap, section height)
PRESETS = [
    (13.0, 16.0, 10.5, 13.0, 5, 26),
    (12.5, 15.0, 10.0, 12.0, 4, 25),
    (12.0, 14.5, 10.0, 12.0, 3, 24),
    (11.5, 14.0, 9.5, 11.5, 3, 23),
    (11.0, 13.0, 9.5, 11.0, 3, 22),
]

# the embedded faces each preset resolves to (headline / summary / brief)
_PRESET_FONTS = [
    ("head13", "sum10", "brief11"),
    ("head12", "sum10", "brief10"),
    ("head12", "sum10", "brief10"),
    ("head11", "sum9", "brief10"),
    ("head11", "sum9", "brief10"),
]


def build_blocks():
    blocks = []
    for name, stories in SECTIONS:
        blocks.append(("sect", name))
        for head, summ in stories:
            blocks.append(("story", (head, summ)))
    blocks.append(("sect", "IN BRIEF"))
    blocks.append(("brief", BUSINESS_BRIEF))
    blocks.append(("brief", SPORT_BRIEF))
    return blocks


def preset_fonts(i):
    hs, hlh, ss, slh, gap, sect_h = PRESETS[i]
    hk, sk, bk = _PRESET_FONTS[i]
    return {
        "head": FONTS[hk],
        "hlh": hlh,
        "sum": FONTS[sk],
        "slh": slh,
        "gap": gap,
        "sect_h": sect_h,
        "sect": FONTS["kicker"],
        "brief": FONTS[bk],
        "blh": slh + 1,
    }


def block_height(kind, payload, F):
    if kind == "sect":
        return F["sect_h"]
    if kind == "story":
        head, summ = payload
        return (len(wrap(head, F["head"], COL_W)) * F["hlh"]
                + len(wrap(summ, F["sum"], COL_W)) * F["slh"] + F["gap"])
    return len(wrap(payload, F["brief"], COL_W)) * F["blh"] + F["gap"] + 2


def fits(blocks, F, cols_height):
    """Simulate the 3-column packing; True if every block lands inside.
    A section header is never left orphaned at a column's foot: it moves
    with at least the block that follows it."""
    col, cy = 0, 0
    for i, (kind, payload) in enumerate(blocks):
        bh = block_height(kind, payload, F)
        need = bh
        if kind == "sect" and i + 1 < len(blocks):
            need += block_height(blocks[i + 1][0], blocks[i + 1][1], F)
        if cy + need > cols_height and col < 2:
            col += 1
            cy = 0
        if cy + bh > cols_height:
            return False
        cy += bh
    return True


# --------------------------------------------------------------------------
# Page construction
# --------------------------------------------------------------------------
def build():
    cv = Canvas(W, H, PAPER)

    f_mast = FONTS["mast"]
    f_date = FONTS["date"]
    f_info = FONTS["info"]
    f_kicker = FONTS["kicker"]
    f_hero = FONTS["hero"]
    f_hero_sum = FONTS["hero_sum"]
    f_byline = FONTS["byline"]
    f_caption = FONTS["caption"]
    f_strip = FONTS["strip"]
    f_foot = FONTS["foot"]

    # --- masthead ---------------------------------------------------------
    cv.line(M, 14, W - M, 14, INK, 1)
    title = "THE DAILY DISPATCH"
    tw = f_mast.length(title)
    draw_text(cv, (W - tw) / 2, 20, title, f_mast, INK)
    cv.line(M, 88, W - M, 88, INK, 3)
    cv.line(M, 93, W - M, 93, INK, 1)

    # --- date / info bar ---------------------------------------------------
    y = 100
    draw_text(cv, M, y + 2, "Vol. I \u00b7 No. 325", f_info, GREY)
    right = "ONE PAGE \u00b7 ONE DAY \u00b7 EVERY STORY"
    draw_text(cv, W - M - f_info.length(right), y + 2, right, f_info, GREY)
    date = "Saturday, 21 November 2026"
    dw = f_date.length(date)
    draw_text(cv, (W - dw) / 2, y, date, f_date, INK)
    y = 126
    cv.line(M, y, W - M, y, INK, 1)

    # --- hero ---------------------------------------------------------------
    hero_top = y + 10
    hero_left_w = 606
    draw_text(cv, M, hero_top, HERO_KICKER, f_kicker, ACCENT)
    hy = draw_wrapped(cv, M, hero_top + 19, HERO_HEADLINE, f_hero, 37, hero_left_w)
    hy += 3
    hy = draw_wrapped(cv, M, hy, HERO_SUMMARY, f_hero_sum, 17, hero_left_w)
    hy += 2
    draw_text(cv, M, hy, HERO_BYLINE, f_byline, GREY)
    hero_text_bottom = hy + 16

    # hero visual box (right)
    vx0, vy0, vx1 = M + hero_left_w + 18, hero_top, W - M
    box_h = 172
    cv.rect_outline(vx0, vy0, vx1, vy0 + box_h, INK, 2)
    draw_text(cv, vx0 + 10, vy0 + 7, "THE DAY IN ONE IMAGE", f_kicker, GREY)
    draw_globe(cv, vx0 + 112, vy0 + box_h // 2 + 8, 72)
    draw_thermometer(cv, vx0 + 262, vy0 + 44, 84)
    cap_y = vy0 + box_h + 6
    cap_bottom = draw_wrapped(cv, vx0, cap_y, HERO_CAPTION, f_caption, 15, vx1 - vx0,
                              fill=GREY, max_lines=3)

    hero_bottom = max(hero_text_bottom, cap_bottom)

    # --- markets strip -------------------------------------------------------
    sy = hero_bottom + 6
    cv.fill_rect(M, sy, W - M, sy + 24, INK)
    segs = list(STRIP_SEGMENTS)
    while len(segs) > 2 and f_strip.length("  ".join(segs)) > CW - 16:
        segs.pop()
    strip = " \u00b7 ".join(segs)
    while len(segs) > 2 and f_strip.length(strip) > CW - 16:
        segs.pop()
        strip = " \u00b7 ".join(segs)
    sw = f_strip.length(strip)
    draw_text(cv, (W - sw) / 2, sy + 5, strip, f_strip, WHITE)
    cols_top = sy + 34
    cols_height = COL_BOTTOM - cols_top

    # --- columns (first preset that fits wins — deterministic) ----------------
    blocks = build_blocks()
    F = None
    for i in range(len(PRESETS)):
        cand = preset_fonts(i)
        if fits(blocks, cand, cols_height):
            F = cand
            break
    if F is None:
        F = preset_fonts(len(PRESETS) - 1)

    col, cy = 0, cols_top
    for i, (kind, payload) in enumerate(blocks):
        bh = block_height(kind, payload, F)
        need = bh
        if kind == "sect" and i + 1 < len(blocks):
            need += block_height(blocks[i + 1][0], blocks[i + 1][1], F)
        if cy + need > COL_BOTTOM and col < 2:
            col += 1
            cy = cols_top
        x = COL_X[col]
        if kind == "sect":
            cv.fill_rect(x, cy + 2, x + COL_W, cy + 20, INK)
            draw_text(cv, x + 7, cy + 4, payload, F["sect"], WHITE)
            cy += F["sect_h"]
        elif kind == "story":
            head, summ = payload
            cy = draw_wrapped(cv, x, cy, head, F["head"], F["hlh"], COL_W)
            cy = draw_wrapped(cv, x, cy, summ, F["sum"], F["slh"], COL_W, fill=DARK)
            cy += F["gap"]
        else:
            cy = draw_wrapped(cv, x, cy, payload, F["brief"], F["blh"], COL_W)
            cy += F["gap"] + 2

    # --- footer ---------------------------------------------------------------
    cv.line(M, H - 28, W - M, H - 28, INK, 1)
    fw = f_foot.length(FOOTER)
    draw_text(cv, (W - fw) / 2, H - 22, FOOTER, f_foot, GREY)

    return cv


# --------------------------------------------------------------------------
# PNG writer (deterministic: fixed filter scoring, fixed zlib level,
# no ancillary chunks, no timestamps)
# --------------------------------------------------------------------------
_FOLD = bytes(b if b < 128 else 256 - b for b in range(256))


def _filter_row(ftype, row, prev):
    if ftype == 0:
        return row
    if ftype == 1:  # Sub
        return row[:3] + bytes((row[i] - row[i - 3]) & 0xFF
                               for i in range(3, len(row)))
    # Up
    return bytes((a - b) & 0xFF for a, b in zip(row, prev))


def png_bytes(cv):
    w, h, px = cv.w, cv.h, cv.px
    stride = w * 3
    raw = bytearray()
    prev = bytes(stride)
    for yy in range(h):
        row = bytes(px[yy * stride:(yy + 1) * stride])
        best = None
        best_score = None
        for ftype in (0, 1, 2):
            filt = _filter_row(ftype, row, prev)
            score = sum(filt.translate(_FOLD))
            if best_score is None or score < best_score:
                best_score = score
                best = bytes((ftype,)) + filt
        raw += best
        prev = row

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(build())
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
