;; ============================================================
;; TROCARCOR v6
;; Comando: TROCARCOR
;;
;; CASO 1 — RGB 0,0,0 (TrueColor 0) em TEXTOS, LINHAS,
;;           POLILINHAS e HATCHS -> substitui por COR 7
;;           (white/black ACI) e remove o grupo 420.
;;
;; CASO 2 — Percorre TODOS os textos de TODAS as layers e:
;;             · RGB 15,15,15 (986895)       -> COR 7
;;             · Qualquer cinza ACI          -> RGB 51,51,51
;;               (tons cinza ACI: 8, 9, 250-255)
;;
;; CASO 3 — Formatação INLINE de MTEXT (grupo 1 / códigos RTF):
;;             · \C8;  \C9;  \C250; ... \C255;
;;               -> substituídos por \c3355443; (RGB 51,51,51)
;;             · \c0;  (TrueColor RGB 0,0,0)
;;               -> substituídos por \C7; (white/black ACI)
;;
;; Tons de cinza ACI considerados:
;;   8, 9  — cinza escuro / cinza médio-escuro
;;   250   — cinza muito escuro
;;   251   — cinza escuro
;;   252   — cinza médio-escuro
;;   253   — cinza médio
;;   254   — cinza claro
;;   255   — cinza muito claro
;; ============================================================

(defun c:TROCARCOR (/ ss i ent dados cor coraci aci cnt1 cnt2 cnt3
                      txt txt2 grp1)

  ;; ----------------------------------------------------------------
  ;; Função auxiliar: retorna T se o valor ACI for um tom de cinza
  ;; Cinzas ACI: 8, 9, 250, 251, 252, 253, 254, 255
  ;; ----------------------------------------------------------------
  (defun cinza-aci-p (v)
    (or (= v 8) (= v 9)
        (and (>= v 250) (<= v 255)))
  )

  ;; ----------------------------------------------------------------
  ;; Função auxiliar: substitui TODAS as ocorrências de OLD por NEW
  ;; dentro da string STR (busca literal, sem regex).
  ;; ----------------------------------------------------------------
  (defun str-replace-all (str old new / pos resultado)
    (setq resultado "")
    (while (setq pos (vl-string-search old str))
      (setq resultado (strcat resultado (substr str 1 pos) new))
      (setq str (substr str (+ pos (strlen old) 1)))
    )
    (strcat resultado str)
  )

  ;; ----------------------------------------------------------------
  ;; Função auxiliar: processa a string RTF de um MTEXT e substitui
  ;; os códigos de cor inline cinza.
  ;;
  ;; Códigos tratados no formato MTEXT RTF:
  ;;   \C<n>;   — cor ACI n       (ex: \C8;)
  ;;   \c<n>;   — cor TrueColor n (ex: \c0;)
  ;;
  ;; Regras de substituição:
  ;;   \C8;  \C9;  \C250; ... \C255;  ->  \c3355443;
  ;;   \c0;                            ->  \C7;
  ;; ----------------------------------------------------------------
  (defun processa-mtext-inline (txt / cinzas-aci c tok novo)
    (setq cinzas-aci '(8 9 250 251 252 253 254 255))

    ;; Substituição: \c0; (TrueColor RGB 0,0,0) -> \C7;
    (setq txt (str-replace-all txt "\\c0;" "\\C7;"))

    ;; Substituição: cada \C<n>; cinza -> \c3355443;
    (foreach c cinzas-aci
      (setq tok (strcat "\\C" (itoa c) ";"))
      (setq txt (str-replace-all txt tok "\\c3355443;"))
    )
    txt
  )

  ;; ================================================================
  ;; CASO 1: RGB 0,0,0 em textos, linhas, polilinhas e hatchs -> COR 7
  ;; ================================================================
  (setq cnt1 0)
  (setq ss (ssget "X" '((0 . "TEXT,MTEXT,LINE,LWPOLYLINE,POLYLINE,HATCH"))))

  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent   (ssname ss i)
              dados (entget ent)
              cor   (assoc 420 dados))

        ;; TrueColor presente e igual a 0 (RGB 0,0,0)?
        (if (and cor (= (cdr cor) 0))
          (progn
            (setq dados (vl-remove cor dados))
            (if (assoc 62 dados)
              (setq dados (subst '(62 . 7) (assoc 62 dados) dados))
              (setq dados (append dados '((62 . 7))))
            )
            (entmod dados)
            (setq cnt1 (1+ cnt1))
          )
        )
        (setq i (1+ i))
      )
    )
  )

  ;; ================================================================
  ;; CASO 2: Todos os textos — cor do objeto inteiro
  ;;   · RGB 15,15,15 (986895) -> COR 7
  ;;   · Cinzas ACI (8,9,250-255) -> RGB 51,51,51 (3355443)
  ;; ================================================================
  (setq cnt2 0)
  (setq ss (ssget "X" '((0 . "TEXT,MTEXT"))))

  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent    (ssname ss i)
              dados  (entget ent)
              cor    (assoc 420 dados)
              coraci (assoc 62  dados))

        ;; --- RGB 15,15,15 -> COR 7 ---
        (if (and cor (= (cdr cor) 986895))
          (progn
            (setq dados (vl-remove cor dados))
            (if (assoc 62 dados)
              (setq dados (subst '(62 . 7) (assoc 62 dados) dados))
              (setq dados (append dados '((62 . 7))))
            )
            (setq cnt2 (1+ cnt2))
          )
        )

        ;; Atualiza referência após possível modificação acima
        (setq coraci (assoc 62 dados))
        (if coraci (setq aci (cdr coraci)) (setq aci -1))

        ;; --- Qualquer cinza ACI (8, 9, 250-255) -> RGB 51,51,51 ---
        (if (cinza-aci-p aci)
          (progn
            (setq dados (vl-remove coraci dados))
            (if (assoc 420 dados)
              (setq dados (subst '(420 . 3355443) (assoc 420 dados) dados))
              (setq dados (append dados '((420 . 3355443))))
            )
            (setq cnt2 (1+ cnt2))
          )
        )

        (entmod dados)
        (setq i (1+ i))
      )
    )
  )

  ;; ================================================================
  ;; CASO 3: Cores INLINE dentro da string RTF do MTEXT
  ;;   · \C8; \C9; \C250-255; -> \c3355443;
  ;;   · \c0;                  -> \C7;
  ;; ================================================================
  (setq cnt3 0)
  (setq ss (ssget "X" '((0 . "MTEXT"))))

  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent   (ssname ss i)
              dados (entget ent)
              grp1  (assoc 1 dados))

        (if grp1
          (progn
            (setq txt  (cdr grp1)
                  txt2 (processa-mtext-inline txt))

            ;; Só modifica se a string realmente mudou
            (if (not (equal txt txt2))
              (progn
                (setq dados (subst (cons 1 txt2) grp1 dados))
                (entmod dados)
                (setq cnt3 (1+ cnt3))
              )
            )
          )
        )
        (setq i (1+ i))
      )
    )
  )

  ;; ----------------------------------------------------------------
  ;; Resumo
  ;; ----------------------------------------------------------------
  (princ (strcat
    "\n--- TROCARCOR concluido ---"
    "\nCASO 1 (RGB 0,0,0 -> COR 7) textos/linhas/polilinhas/hatchs : "
    (itoa cnt1) " objeto(s)."
    "\nCASO 2 (RGB 15,15,15 -> COR 7 / cinzas ACI -> RGB 51,51,51) textos: "
    (itoa cnt2) " objeto(s)."
    "\nCASO 3 (cores inline MTEXT): "
    (itoa cnt3) " MTEXT(s) com string alterada."
  ))
  (princ)
)
