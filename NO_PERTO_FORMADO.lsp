;; NO_PERTO_FORMADO.lsp
;; Compativel com AutoCAD e NanoCAD 5+
;;
;; DESCRICAO:
;;   Percorre o Model Space e identifica pares formados por:
;;     - Uma LWPOLYLINE fechada com area ~2.6437 na layer COR_000000
;;     - Um HATCH solido com area ~2.6437 na layer COR_000000
;;   Converte cada par no bloco NO_PERTO_FORMADO usando VLA CopyObjects
;;   (sem comandos interativos, sem dialogs).
;;
;; USO: Carregue o arquivo e execute NOPERTO.
;; DIAGNOSTICO: Execute NOPERTO_DIAG para ver areas e layers reais.

(vl-load-com)

;;; =========================================================================
;;; PARAMETROS GLOBAIS  (resetados a cada carregamento)
;;; =========================================================================
(setq *NPF_LAYER*      "COR_000000")
(setq *NPF_AREA*        2.6437)   ; area original de identificacao
(setq *NPF_AREA_ALVO*   0.6761)   ; area alvo apos redimensionamento
(setq *NPF_TOL_AREA*    0.010)    ; tolerancia de area (+/-)
(setq *NPF_TOLERANCIA*  0.5)      ; distancia max entre centros do par
(setq *NPF_NOME_BLOCO* "NO_PERTO_FORMADO")

;;; =========================================================================
;;; AREA
;;; =========================================================================

(defun npf-area-shoelace (en / ed pts n i p1 p2 soma)
  (setq ed   (entget en)
        pts  (mapcar 'cdr (vl-remove-if-not (lambda (x) (= (car x) 10)) ed))
        n    (length pts)
        soma 0.0)
  (if (>= n 3)
    (progn
      (setq i 0)
      (repeat n
        (setq p1   (nth i pts)
              p2   (nth (rem (1+ i) n) pts)
              soma (+ soma (- (* (car p1) (cadr p2)) (* (car p2) (cadr p1))))
              i    (1+ i)))
      (abs (/ soma 2.0)))
    0.0)
)

(defun npf-get-area (en / obj av result ed)
  (setq result nil)
  (if (and en (entget en))
    (progn
      (setq obj (vlax-ename->vla-object en))
      (setq av  (vl-catch-all-apply (lambda () (vla-get-Area obj)) nil))
      (if (and av (not (vl-catch-all-error-p av)) (> av 0.0))
        (setq result av)
        (progn
          (setq ed (entget en))
          (if (= (cdr (assoc 0 ed)) "LWPOLYLINE")
            (progn
              (setq result (npf-area-shoelace en))
              (if (= result 0.0) (setq result nil))))))))
  result
)

(defun npf-area-valida? (en area-ref tol / v)
  (setq v (npf-get-area en))
  (and v (>= v (- area-ref tol)) (<= v (+ area-ref tol)))
)

;;; =========================================================================
;;; CENTRO (bounding-box VLA; fallback media de vertices)
;;; =========================================================================

(defun npf-centro-entidade (en / obj mn mx cx cy ed pts n sx sy r)
  (setq r nil  obj (vlax-ename->vla-object en))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply
               (lambda ()
                 (vla-getboundingbox obj 'mn 'mx)
                 (setq mn (vlax-safearray->list mn)
                       mx (vlax-safearray->list mx)
                       cx (/ (+ (car mn) (car mx)) 2.0)
                       cy (/ (+ (cadr mn) (cadr mx)) 2.0)
                       r  (list cx cy 0.0)))
               nil)))
    r
    (progn
      (setq ed  (entget en)
            pts (vl-remove-if-not (lambda (x) (= (car x) 10)) ed)
            n   (length pts)  sx 0.0  sy 0.0)
      (if (> n 0)
        (progn
          (foreach pt pts
            (setq sx (+ sx (cadr pt)) sy (+ sy (caddr pt))))
          (list (/ sx n) (/ sy n) 0.0))
        nil))
  )
)

(defun npf-dist2d (p1 p2)
  (sqrt (+ (expt (- (car p2) (car p1)) 2) (expt (- (cadr p2) (cadr p1)) 2)))
)

;;; Redimensiona poly e hatch de um par para que a area resultante
;;; seja *NPF_AREA_ALVO*. O fator linear e calculado como:
;;;   escala = sqrt(area_alvo / area_real)
;;; Ambas as entidades sao escaladas em torno do centro do par.
(defun npf-escalar-par (en-poly en-hatch centro area-alvo
                         / area-real escala pt-base obj-poly obj-hatch err)
  ;; Calcula a area real da polilinha (referencia)
  (setq area-real (npf-get-area en-poly))
  (if (and area-real (> area-real 0.0))
    (progn
      (setq escala  (sqrt (/ area-alvo area-real))
            pt-base (vlax-3d-point (car centro) (cadr centro) 0.0)
            obj-poly  (vlax-ename->vla-object en-poly)
            obj-hatch (vlax-ename->vla-object en-hatch))

      ;; Escala a polilinha
      (setq err (vl-catch-all-apply
                  (lambda () (vla-ScaleEntity obj-poly pt-base escala))
                  nil))
      (if (vl-catch-all-error-p err)
        (princ (strcat "\n  [AVISO] Falha ao escalar polilinha: "
                       (vl-catch-all-error-message err))))

      ;; Escala o hatch
      (setq err (vl-catch-all-apply
                  (lambda () (vla-ScaleEntity obj-hatch pt-base escala))
                  nil))
      (if (vl-catch-all-error-p err)
        (princ (strcat "\n  [AVISO] Falha ao escalar hatch: "
                       (vl-catch-all-error-message err))))

      (princ (strcat "  escala=" (rtos escala 2 6)
                     " area_orig=" (rtos area-real 2 6)
                     " -> alvo=" (rtos area-alvo 2 6)))
      T
    )
    (progn
      (princ "\n  [AVISO] Nao foi possivel calcular a area para escalonamento.")
      nil)
  )
)

;;; =========================================================================
;;; CRIACAO DO BLOCO via VLA CopyObjects  (sem comandos, sem dialogs)
;;;
;;; Cria uma nova definicao de bloco e copia poly + hatch para dentro dela.
;;; Retorna T em caso de sucesso, nil em caso de falha.
;;; =========================================================================
(defun npf-criar-bloco-vla (nome-bloco centro en-poly en-hatch
                             / doc blocos blk-def pt-base
                               obj-poly obj-hatch arr-src err)
  (setq doc    (vla-get-ActiveDocument (vlax-get-acad-object))
        blocos (vla-get-Blocks doc))

  ;; Ponto base do bloco como objeto 3D VLA
  (setq pt-base (vlax-3d-point (car centro) (cadr centro) 0.0))

  ;; Cria a definicao vazia do bloco
  (setq err
    (vl-catch-all-apply
      (lambda ()
        (setq blk-def (vla-Add blocos pt-base nome-bloco)))
      nil))

  (if (vl-catch-all-error-p err)
    (progn
      (princ (strcat "\n[ERRO] Nao foi possivel criar a definicao do bloco: "
                     (vl-catch-all-error-message err)))
      nil)
    (progn
      ;; Objetos VLA das entidades originais
      (setq obj-poly  (vlax-ename->vla-object en-poly)
            obj-hatch (vlax-ename->vla-object en-hatch))

      ;; Monta safearray com as 2 entidades
      (setq arr-src (vlax-make-safearray vlax-vbObject '(0 . 1)))
      (vlax-safearray-put-element arr-src 0 obj-poly)
      (vlax-safearray-put-element arr-src 1 obj-hatch)

      ;; Copia as entidades para dentro da definicao do bloco
      (setq err
        (vl-catch-all-apply
          (lambda () (vla-CopyObjects doc arr-src blk-def))
          nil))

      (if (vl-catch-all-error-p err)
        (progn
          (princ (strcat "\n[ERRO] Falha ao copiar entidades para o bloco: "
                         (vl-catch-all-error-message err)))
          ;; Remove a definicao vazia para nao sujar o desenho
          (vl-catch-all-apply (lambda () (vla-Delete blk-def)) nil)
          nil)
        (progn
          (princ (strcat "\n> Bloco '" nome-bloco "' criado com sucesso."))
          T)
      )
    )
  )
)

;;; =========================================================================
;;; INSERCAO DE REFERENCIA DE BLOCO  (entmake simples para INSERT)
;;; =========================================================================
(defun npf-inserir-bloco (nome-bloco ponto layer-nome)
  (entmake
    (list
      '(0   . "INSERT")
      '(100 . "AcDbEntity")
      (cons 8 layer-nome)
      '(100 . "AcDbBlockReference")
      (cons 2 nome-bloco)
      (cons 10 ponto)
      '(41 . 1.0)
      '(42 . 1.0)
      '(43 . 1.0)
      '(50 . 0.0)
    ))
)

;;; =========================================================================
;;; COMANDO PRINCIPAL: NOPERTO
;;; =========================================================================
(defun run-no-perto-formado
  (/ doc lista-poly lista-hatch
     ss-poly-raw ss-hatch-raw
     i en centro-val
     en-poly en-hatch
     centro-poly centro-hatch
     dist dist-minima
     pares par
     hatches-usados
     melhor-hatch melhor-dist
     total-pares n-convertidos
     bloco-existe centro)

  (vl-load-com)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))

  (princ "\n====================================================")
  (princ (strcat "\n  NO_PERTO_FORMADO  |  Layer: " *NPF_LAYER*))
  (princ (strcat "\n  Area: " (rtos *NPF_AREA* 2 4)
                 " +/- " (rtos *NPF_TOL_AREA* 2 4)))
  (princ "\n====================================================")

  ;; ----------------------------------------------------------------
  ;; 1. Coleta e filtra LWPOLYLINES por area
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 1: Buscando polilinhas...")
  (setq ss-poly-raw
    (ssget "X" (list '(0 . "LWPOLYLINE") (cons 8 *NPF_LAYER*) '(410 . "Model"))))
  (setq lista-poly '())
  (if ss-poly-raw
    (progn
      (setq i 0)
      (repeat (sslength ss-poly-raw)
        (setq en (ssname ss-poly-raw i))
        (if (npf-area-valida? en *NPF_AREA* *NPF_TOL_AREA*)
          (progn
            (setq centro-val (npf-centro-entidade en))
            (if centro-val
              (setq lista-poly
                (append lista-poly
                  (list (list (cons "en" en) (cons "c" centro-val))))))))
        (setq i (1+ i)))))
  (princ (strcat "\n> " (itoa (length lista-poly)) " polilinha(s) encontrada(s)."))
  (if (= (length lista-poly) 0)
    (progn (princ "\n[AVISO] Nenhuma polilinha. Execute NOPERTO_DIAG.") (princ) (exit)))

  ;; ----------------------------------------------------------------
  ;; 2. Coleta e filtra HATCHES por area
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 2: Buscando hatches...")
  (setq ss-hatch-raw
    (ssget "X" (list '(0 . "HATCH") (cons 8 *NPF_LAYER*) '(410 . "Model"))))
  (setq lista-hatch '())
  (if ss-hatch-raw
    (progn
      (setq i 0)
      (repeat (sslength ss-hatch-raw)
        (setq en (ssname ss-hatch-raw i))
        (if (npf-area-valida? en *NPF_AREA* *NPF_TOL_AREA*)
          (progn
            (setq centro-val (npf-centro-entidade en))
            (if centro-val
              (setq lista-hatch
                (append lista-hatch
                  (list (list (cons "en" en) (cons "c" centro-val))))))))
        (setq i (1+ i)))))
  (princ (strcat "\n> " (itoa (length lista-hatch)) " hatch(es) encontrado(s)."))
  (if (= (length lista-hatch) 0)
    (progn (princ "\n[AVISO] Nenhum hatch. Execute NOPERTO_DIAG.") (princ) (exit)))

  ;; ----------------------------------------------------------------
  ;; 3. Emparelhamento por vizinho mais proximo
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 3: Emparelhando por vizinho mais proximo...")
  (setq pares '()  hatches-usados '()  dist-minima 999999.0)

  (foreach item-poly lista-poly
    (setq en-poly     (cdr (assoc "en" item-poly))
          centro-poly (cdr (assoc "c"  item-poly))
          melhor-hatch nil
          melhor-dist  999999.0)

    (foreach item-hatch lista-hatch
      (setq en-hatch     (cdr (assoc "en" item-hatch))
            centro-hatch (cdr (assoc "c"  item-hatch)))
      (if (not (member en-hatch hatches-usados))
        (progn
          (setq dist (npf-dist2d centro-poly centro-hatch))
          (if (< dist dist-minima) (setq dist-minima dist))
          (if (< dist melhor-dist)
            (setq melhor-dist  dist
                  melhor-hatch en-hatch)))))

    (if (and melhor-hatch (<= melhor-dist *NPF_TOLERANCIA*))
      (progn
        (setq hatches-usados (cons melhor-hatch hatches-usados))
        (setq pares (append pares
                      (list (list (cons "poly"   en-poly)
                                  (cons "hatch"  melhor-hatch)
                                  (cons "centro" centro-poly))))))))

  (setq total-pares (length pares))
  (if (= total-pares 0)
    (progn
      (princ "\n[AVISO] Nenhum par encontrado.")
      (princ (strcat "\n  Tol. centro: " (rtos *NPF_TOLERANCIA* 2 4) " un."))
      (princ (strcat "\n  Menor dist.: " (rtos dist-minima 2 6) " un."))
      (princ)
      (exit)))
  (princ (strcat "\n> " (itoa total-pares) " par(es) encontrado(s)."))

  ;; ----------------------------------------------------------------
  ;; 4. Redimensiona cada par para a area alvo (*NPF_AREA_ALVO*)
  ;; ----------------------------------------------------------------
  (princ (strcat "\nEtapa 4: Redimensionando para area alvo "
                 (rtos *NPF_AREA_ALVO* 2 4) "..."))
  (foreach par pares
    (setq en-poly  (cdr (assoc "poly"   par))
          en-hatch (cdr (assoc "hatch"  par))
          centro   (cdr (assoc "centro" par)))
    (princ (strcat "\n  Par em (" (rtos (car centro) 2 2) ","
                   (rtos (cadr centro) 2 2) "):  "))
    (if (and (entget en-poly) (entget en-hatch))
      (npf-escalar-par en-poly en-hatch centro *NPF_AREA_ALVO*)
      (princ "[AVISO] Entidade ausente, par ignorado."))
  )

  ;; ----------------------------------------------------------------
  ;; 5. Cria bloco e insere referencias
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 5: Convertendo pares em blocos...")

  (setq n-convertidos 0
        bloco-existe (tblsearch "BLOCK" *NPF_NOME_BLOCO*))

  (foreach par pares
    (setq en-poly  (cdr (assoc "poly"   par))
          en-hatch (cdr (assoc "hatch"  par))
          centro   (cdr (assoc "centro" par)))

    ;; Verifica se entidades ainda existem
    (if (and (entget en-poly) (entget en-hatch))
      (progn
        (if (not bloco-existe)
          ;; Cria a definicao do bloco (apenas 1 vez)
          (progn
            (setq bloco-existe
              (npf-criar-bloco-vla *NPF_NOME_BLOCO* centro en-poly en-hatch))
            (if bloco-existe
              (progn
                ;; Apaga os originais que foram copiados para o bloco
                (if (entget en-hatch) (entdel en-hatch))
                (if (entget en-poly)  (entdel en-poly))
                ;; Insere referencia no centro
                (npf-inserir-bloco *NPF_NOME_BLOCO* centro *NPF_LAYER*)
                (setq n-convertidos (1+ n-convertidos))
                (princ (strcat "\n  [" (itoa n-convertidos) "/" (itoa total-pares)
                               "] Inserido em ("
                               (rtos (car centro) 2 2) ","
                               (rtos (cadr centro) 2 2) ")."))))
          )
          ;; Bloco ja existe: apenas apaga originais e insere referencia
          (progn
            (if (entget en-hatch) (entdel en-hatch))
            (if (entget en-poly)  (entdel en-poly))
            (npf-inserir-bloco *NPF_NOME_BLOCO* centro *NPF_LAYER*)
            (setq n-convertidos (1+ n-convertidos))
            (princ (strcat "\n  [" (itoa n-convertidos) "/" (itoa total-pares)
                           "] Inserido em ("
                           (rtos (car centro) 2 2) ","
                           (rtos (cadr centro) 2 2) ")."))
          )
        )
      )
      (princ "\n  [AVISO] Par ignorado: entidade ja inexistente.")
    )
  )

  ;; ----------------------------------------------------------------
  ;; 5. Resumo
  ;; ----------------------------------------------------------------
  (princ "\n====================================================")
  (princ (strcat "\n  CONCLUIDO: " (itoa n-convertidos)
                 " bloco(s) '" *NPF_NOME_BLOCO* "' inserido(s)."))
  (if (< n-convertidos total-pares)
    (princ (strcat "\n  ATENCAO: "
                   (itoa (- total-pares n-convertidos))
                   " par(es) nao convertido(s).")))
  (princ "\n====================================================")
  (command "_.REGEN")
  (princ)
)

;;; =========================================================================
;;; NOPERTO_CONFIG
;;; =========================================================================
(defun c:NOPERTO_CONFIG (/ nl na nta nt naa)
  (princ "\n=== NOPERTO CONFIG ===")
  (princ (strcat "\n Layer      : " *NPF_LAYER*))
  (princ (strcat "\n Area orig. : " (rtos *NPF_AREA*       2 4)))
  (princ (strcat "\n Area alvo  : " (rtos *NPF_AREA_ALVO*  2 4)))
  (princ (strcat "\n Tol. area  : " (rtos *NPF_TOL_AREA*   2 4)))
  (princ (strcat "\n Tol. cen.  : " (rtos *NPF_TOLERANCIA* 2 4)))
  (princ (strcat "\n Bloco      : " *NPF_NOME_BLOCO*))
  (setq nl (getstring (strcat "\nLayer <" *NPF_LAYER* ">: ")))
  (if (/= (vl-string-trim " " nl) "") (setq *NPF_LAYER* (vl-string-trim " " nl)))
  (setq na (getreal (strcat "\nArea identificacao <" (rtos *NPF_AREA* 2 4) ">: ")))
  (if na (setq *NPF_AREA* na))
  (setq naa (getreal (strcat "\nArea alvo (reduzida) <" (rtos *NPF_AREA_ALVO* 2 4) ">: ")))
  (if naa (setq *NPF_AREA_ALVO* naa))
  (setq nta (getreal (strcat "\nTol. area +/- <" (rtos *NPF_TOL_AREA* 2 4) ">: ")))
  (if nta (setq *NPF_TOL_AREA* nta))
  (setq nt (getdist (strcat "\nTol. centro <" (rtos *NPF_TOLERANCIA* 2 4) ">: ")))
  (if nt (setq *NPF_TOLERANCIA* nt))
  (princ "\n=== Atualizado ===")
  (princ)
)

;;; =========================================================================
;;; NOPERTO_RESET
;;; =========================================================================
(defun c:NOPERTO_RESET ()
  (setq *NPF_LAYER*      "COR_000000"
        *NPF_AREA*        2.6437
        *NPF_AREA_ALVO*   0.6761
        *NPF_TOL_AREA*    0.010
        *NPF_TOLERANCIA*  0.5
        *NPF_NOME_BLOCO* "NO_PERTO_FORMADO")
  (princ "\n[NOPERTO_RESET] Parametros resetados.")
  (princ (strcat "\n  Layer: " *NPF_LAYER*
                 "  Area orig: " (rtos *NPF_AREA*      2 4)
                 "  Area alvo: " (rtos *NPF_AREA_ALVO* 2 4)
                 "  Tol.area: "  (rtos *NPF_TOL_AREA*  2 4)
                 "  Tol.cen: "   (rtos *NPF_TOLERANCIA* 2 4)))
  (princ)
)

;;; =========================================================================
;;; NOPERTO_DIAG
;;; =========================================================================
(defun c:NOPERTO_DIAG (/ ss en i ed layer av n)
  (vl-load-com)
  (princ "\n=== NOPERTO_DIAG ===")
  (princ "\n--- LWPOLYLINES ---")
  (setq ss (ssget "X" '((0 . "LWPOLYLINE") (410 . "Model"))) n 0)
  (if ss
    (progn
      (setq i 0)
      (repeat (sslength ss)
        (setq en (ssname ss i) ed (entget en)
              av (npf-get-area en) layer (cdr (assoc 8 ed)))
        (princ (strcat "\n  [" layer "]  Area: "
                       (if av (rtos av 2 6) "(nao calculada)")))
        (setq i (1+ i) n (1+ n))))
    (princ "\n  Nenhuma encontrada."))
  (princ (strcat "\n  Total: " (itoa n)))
  (princ "\n--- HATCHES ---")
  (setq ss (ssget "X" '((0 . "HATCH") (410 . "Model"))) n 0)
  (if ss
    (progn
      (setq i 0)
      (repeat (sslength ss)
        (setq en (ssname ss i) ed (entget en)
              av (npf-get-area en) layer (cdr (assoc 8 ed)))
        (princ (strcat "\n  [" layer "]  Area: "
                       (if av (rtos av 2 6) "(nao calculada)")))
        (setq i (1+ i) n (1+ n))))
    (princ "\n  Nenhum encontrado."))
  (princ (strcat "\n  Total: " (itoa n)))
  (princ "\n====================")
  (princ)
)


;;; =========================================================================
;;; PARAMETROS GLOBAIS - POSTE_EXISTENTE_FORMADO / POSTE_EXISTENTE_ATERRADO
;;;
;;; Tres tipos de par (quadrado fechado + linha interna):
;;;   Tipo A  →  POSTE_EXISTENTE_FORMADO   (area~17.9521  len~4.0265)
;;;   Tipo B  →  POSTE_EXISTENTE_ATERRADO  (area~17.2936  len~3.9918)
;;;   Tipo C  →  POSTE_EXISTENTE_ATERRADO  (area~17.2805  len~3.9953)
;;;
;;; A angulacao individual de cada conjunto e preservada:
;;;   a definicao do bloco e criada com a geometria do 1o par encontrado;
;;;   cada insercao subsequente usa rotacao = (ang_atual - ang_referencia).
;;; =========================================================================
(setq *PEF_LAYER*        "COR_000000")
(setq *PEF_AREA_A*       17.9521)   ; area quadrado tipo A → FORMADO
(setq *PEF_LEN_A*         4.0265)   ; comprimento linha tipo A
(setq *PEF_AREA_B*       17.2936)   ; area quadrado tipo B → ATERRADO
(setq *PEF_LEN_B*         3.9918)   ; comprimento linha tipo B
(setq *PEF_AREA_C*       17.2805)   ; area quadrado tipo C → ATERRADO
(setq *PEF_LEN_C*         3.9953)   ; comprimento linha tipo C
(setq *PEF_TOL_AREA*      0.15)     ; tolerancia de area (+/-)
(setq *PEF_TOL_LEN*       0.10)     ; tolerancia de comprimento (+/-)
(setq *PEF_LAYER_ATER*   "COR_994533") ; layer dos fios de aterramento
(setq *PEF_LEN_ATER_1*   1.3051)
(setq *PEF_LEN_ATER_2*   2.0872)
(setq *PEF_LEN_ATER_3*   1.4571)
(setq *PEF_LEN_ATER_4*   1.0432)
(setq *PEF_NOME_FORMADO*  "POSTE_EXISTENTE_FORMADO")
(setq *PEF_NOME_ATERRADO* "POSTE_EXISTENTE_ATERRADO")

;;; =========================================================================
;;; FUNCOES AUXILIARES - POSTEEF
;;; =========================================================================

;;; Comprimento de uma LWPOLYLINE ou LINE
(defun pef-get-comprimento (en / obj len ed p1 p2)
  (setq obj (vlax-ename->vla-object en))
  (setq len (vl-catch-all-apply (lambda () (vla-get-Length obj)) nil))
  (if (and len (not (vl-catch-all-error-p len)) (> len 0.0))
    len
    (progn
      (setq ed (entget en))
      (if (= (cdr (assoc 0 ed)) "LINE")
        (progn
          (setq p1 (cdr (assoc 10 ed)) p2 (cdr (assoc 11 ed)))
          (sqrt (+ (expt (- (car p2) (car p1)) 2)
                   (expt (- (cadr p2) (cadr p1)) 2))))
        nil)))
)

;;; Bounding-box como lista (mn mx) onde mn=(xmin ymin) mx=(xmax ymax)
(defun pef-get-bbox (en / obj mn mx)
  (setq obj (vlax-ename->vla-object en))
  (if (not (vl-catch-all-error-p
             (vl-catch-all-apply
               (lambda ()
                 (vla-getboundingbox obj 'mn 'mx)
                 (setq mn (vlax-safearray->list mn)
                       mx (vlax-safearray->list mx)))
               nil)))
    (list mn mx) nil)
)

;;; Verifica se pt=(X Y) esta dentro da bbox [mn mx] com folga minima
(defun pef-dentro-bbox? (pt mn mx)
  (and (>= (car  pt) (- (car  mn) 0.001))
       (<= (car  pt) (+ (car  mx) 0.001))
       (>= (cadr pt) (- (cadr mn) 0.001))
       (<= (cadr pt) (+ (cadr mx) 0.001)))
)

;;; Ponto medio: primeiro/ultimo vertice de LINE ou bbox-center de LWPOLYLINE
(defun pef-midpoint (en / ed tipo p1 p2)
  (setq ed (entget en) tipo (cdr (assoc 0 ed)))
  (if (= tipo "LINE")
    (progn
      (setq p1 (cdr (assoc 10 ed)) p2 (cdr (assoc 11 ed)))
      (list (/ (+ (car p1) (car p2)) 2.0)
            (/ (+ (cadr p1) (cadr p2)) 2.0) 0.0))
    (npf-centro-entidade en))
)

;;; Angulo da primeira aresta de um LWPOLYLINE ou LINE (em radianos).
;;; Usado para preservar a angulacao original na insercao do bloco.
(defun pef-get-angulo (en / ed tipo pts p0 p1)
  (setq ed (entget en) tipo (cdr (assoc 0 ed)))
  (cond
    ((= tipo "LWPOLYLINE")
     (setq pts (mapcar 'cdr (vl-remove-if-not (lambda (x) (= (car x) 10)) ed)))
     (if (>= (length pts) 2)
       (progn
         (setq p0 (car pts) p1 (cadr pts))
         (atan (- (cadr p1) (cadr p0)) (- (car p1) (car p0))))
       0.0))
    ((= tipo "LINE")
     (setq p0 (cdr (assoc 10 ed)) p1 (cdr (assoc 11 ed)))
     (atan (- (cadr p1) (cadr p0)) (- (car p1) (car p0))))
    (T 0.0))
)

;;; Retorna o angulo da primeira polyline ou linha contida na definicao de um bloco
(defun pef-get-block-angle (nome-bloco / doc blks blk ang obj en)
  (setq doc  (vla-get-ActiveDocument (vlax-get-acad-object))
        blks (vla-get-Blocks doc)
        ang  nil)
  (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-Item (list blks nome-bloco))))
    (progn
      (setq blk (vla-Item blks nome-bloco))
      (vlax-for obj blk
        (if (not ang)
          (progn
            (setq en (vlax-vla-object->ename obj))
            (if (or (= (cdr (assoc 0 (entget en))) "LWPOLYLINE")
                    (= (cdr (assoc 0 (entget en))) "LINE"))
              (setq ang (pef-get-angulo en))
            )
          )
        )
      )
    )
  )
  (if ang ang 0.0)
)

;;; Identifica o tipo (A/B/C/nil) de um par pela menor distancia normalizada
;;; combinando erro de area e erro de comprimento.
;;; Garante que B e C (areas proximas) sejam distinguidos pelo comprimento.
(defun pef-identificar-tipo (area len
                              / ea eb ec la lb lc da db dc)
  (setq ea (abs (- area *PEF_AREA_A*))
        eb (abs (- area *PEF_AREA_B*))
        ec (abs (- area *PEF_AREA_C*))
        la (abs (- len  *PEF_LEN_A*))
        lb (abs (- len  *PEF_LEN_B*))
        lc (abs (- len  *PEF_LEN_C*)))
  ;; Score combinado normalizado; menor score = melhor tipo
  (setq da (+ (/ ea *PEF_TOL_AREA*) (/ la *PEF_TOL_LEN*))
        db (+ (/ eb *PEF_TOL_AREA*) (/ lb *PEF_TOL_LEN*))
        dc (+ (/ ec *PEF_TOL_AREA*) (/ lc *PEF_TOL_LEN*)))
  ;; Aceita apenas se o score total for <= 2.0 (dentro das tolerancias)
  (cond
    ((and (<= da db) (<= da dc) (<= da 2.0)) "A")
    ((and (<= db da) (<= db dc) (<= db 2.0)) "B")
    ((and (<= dc da) (<= dc db) (<= dc 2.0)) "C")
    (T nil))
)

;;; Encontra as 4 linhas de aterramento perto do centro
(defun pef-achar-aterramentos (centro lista-ater tol-len tol-dist / dist cand e1 e2 e3 e4 l e)
  (setq cand '())
  (foreach item lista-ater
    (setq dist (sqrt (+ (expt (- (car centro) (car (cdr (assoc "centro" item)))) 2)
                        (expt (- (cadr centro) (cadr (cdr (assoc "centro" item)))) 2))))
    (if (<= dist tol-dist)
      (setq cand (cons item cand))))
  
  (setq e1 nil e2 nil e3 nil e4 nil)
  (foreach c cand
    (setq l (cdr (assoc "len" c)) e (cdr (assoc "en" c)))
    (cond
      ((and (not e1) (<= (abs (- l *PEF_LEN_ATER_1*)) tol-len)) (setq e1 e))
      ((and (not e2) (<= (abs (- l *PEF_LEN_ATER_2*)) tol-len)) (setq e2 e))
      ((and (not e3) (<= (abs (- l *PEF_LEN_ATER_3*)) tol-len)) (setq e3 e))
      ((and (not e4) (<= (abs (- l *PEF_LEN_ATER_4*)) tol-len)) (setq e4 e))
    )
  )
  (if (and e1 e2 e3 e4)
    (list e1 e2 e3 e4)
    nil)
)

;;; Cria definicao de bloco com N entidades via VLA CopyObjects.
;;; Retorna T ou nil.
(defun pef-criar-bloco-vla (nome-bloco base-pt lista-ents
                              / doc blocos blk-def pt3d arr err i obj)
  (setq doc    (vla-get-ActiveDocument (vlax-get-acad-object))
        blocos (vla-get-Blocks doc))
  (setq pt3d (vlax-3d-point (car base-pt) (cadr base-pt) 0.0))
  (setq err (vl-catch-all-apply
              (lambda () (setq blk-def (vla-Add blocos pt3d nome-bloco)))
              nil))
  (if (vl-catch-all-error-p err)
    (progn
      (princ (strcat "\n[ERRO] Nao foi possivel criar bloco '"
                     nome-bloco "': " (vl-catch-all-error-message err)))
      nil)
    (progn
      (setq arr (vlax-make-safearray vlax-vbObject (cons 0 (1- (length lista-ents)))))
      (setq i 0)
      (foreach en lista-ents
        (setq obj (vlax-ename->vla-object en))
        (vlax-safearray-put-element arr i obj)
        (setq i (1+ i)))
      (setq err (vl-catch-all-apply
                  (lambda () (vla-CopyObjects doc arr blk-def))
                  nil))
      (if (vl-catch-all-error-p err)
        (progn
          (princ (strcat "\n[ERRO] Falha ao copiar entidades: "
                         (vl-catch-all-error-message err)))
          (vl-catch-all-apply (lambda () (vla-Delete blk-def)) nil)
          nil)
        (progn
          (princ (strcat "\n> Bloco '" nome-bloco "' criado."))
          T)))
  )
)

;;; Insere referencia de bloco com rotacao (em radianos)
(defun pef-inserir-bloco (nome-bloco ponto rotacao layer-nome)
  (entmake
    (list
      '(0   . "INSERT")
      '(100 . "AcDbEntity")
      (cons 8 layer-nome)
      '(100 . "AcDbBlockReference")
      (cons 2  nome-bloco)
      (cons 10 ponto)
      '(41 . 1.0)
      '(42 . 1.0)
      '(43 . 1.0)
      (cons 50 rotacao)      ; rotacao em radianos
    ))
)

;;; =========================================================================
;;; COMANDO PRINCIPAL: POSTEEF
;;; =========================================================================
(defun run-poste-existente
  (/ ss-quad ss-linha
     lista-quad lista-linha
     i en area-val len-val tipo-val
     centro-val bbox-val ang-val
     en-quad en-linha
     centro-quad bbox-quad ang-quad
     mid-linha
     pares par linhas-usadas
     total-pares n-formado n-aterrado
     bloco-formado-existe bloco-aterrado-existe
     ang-ref-formado ang-ref-aterrado
     nome-bloco rotacao-insert
     centro)

  (vl-load-com)

  (princ "\n====================================================")
  (princ "\n  POSTE_EXISTENTE - Identificacao e criacao de blocos")
  (princ (strcat "\n  Layer: " *PEF_LAYER*))
  (princ (strcat "\n  Tipo A → FORMADO  : area~" (rtos *PEF_AREA_A* 2 4)
                 "  len~" (rtos *PEF_LEN_A* 2 4)))
  (princ (strcat "\n  Tipo B → ATERRADO : area~" (rtos *PEF_AREA_B* 2 4)
                 "  len~" (rtos *PEF_LEN_B* 2 4)))
  (princ (strcat "\n  Tipo C → ATERRADO : area~" (rtos *PEF_AREA_C* 2 4)
                 "  len~" (rtos *PEF_LEN_C* 2 4)))
  (princ "\n====================================================")

  ;; ----------------------------------------------------------------
  ;; 1. Coleta todos os quadrados na faixa de area geral [17.0, 18.5]
  ;;    O tipo exato sera determinado em conjunto com o comprimento da linha.
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 1: Buscando quadrados (polilinhas fechadas)...")

  (setq ss-quad
    (ssget "X" (list '(0 . "LWPOLYLINE")
                     (cons 8 *PEF_LAYER*)
                     '(410 . "Model"))))

  (setq lista-quad '())
  (if ss-quad
    (progn
      (setq i 0)
      (repeat (sslength ss-quad)
        (setq en (ssname ss-quad i))
        (setq area-val (npf-get-area en))
        ;; Pre-filtra: area dentro da faixa geral dos tres tipos
        (if (and area-val
                 (>= area-val (- (min *PEF_AREA_A* *PEF_AREA_B* *PEF_AREA_C*)
                                  *PEF_TOL_AREA*))
                 (<= area-val (+ (max *PEF_AREA_A* *PEF_AREA_B* *PEF_AREA_C*)
                                  *PEF_TOL_AREA*)))
          (progn
            (setq centro-val (npf-centro-entidade en)
                  bbox-val   (pef-get-bbox en)
                  ang-val    (pef-get-angulo en))
            (if (and centro-val bbox-val)
              (setq lista-quad
                (append lista-quad
                  (list (list (cons "en"     en)
                              (cons "area"   area-val)
                              (cons "centro" centro-val)
                              (cons "bbox"   bbox-val)
                              (cons "ang"    ang-val))))))))
        (setq i (1+ i)))))

  (princ (strcat "\n> " (itoa (length lista-quad))
                 " quadrado(s) pre-selecionado(s) na faixa de area."))
  (if (= (length lista-quad) 0)
    (progn
      (princ "\n[AVISO] Nenhum quadrado encontrado.")
      (princ "\n  Execute NOPERTO_DIAG para verificar as areas.")
      (princ) (exit)))

  ;; ----------------------------------------------------------------
  ;; 2. Coleta todas as linhas na faixa de comprimento geral [3.8, 4.2]
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 2: Buscando linhas internas...")

  (setq ss-linha
    (ssget "X" (list (cons 0 "LWPOLYLINE,LINE")
                     (cons 8 *PEF_LAYER*)
                     '(410 . "Model"))))

  (setq lista-linha '())
  (if ss-linha
    (progn
      (setq i 0)
      (repeat (sslength ss-linha)
        (setq en (ssname ss-linha i))
        (setq len-val (pef-get-comprimento en))
        (if (and len-val
                 (>= len-val (- (min *PEF_LEN_A* *PEF_LEN_B* *PEF_LEN_C*)
                                 *PEF_TOL_LEN*))
                 (<= len-val (+ (max *PEF_LEN_A* *PEF_LEN_B* *PEF_LEN_C*)
                                 *PEF_TOL_LEN*)))
          (progn
            (setq centro-val (pef-midpoint en))
            (if centro-val
              (setq lista-linha
                (append lista-linha
                  (list (list (cons "en"     en)
                              (cons "len"    len-val)
                              (cons "centro" centro-val))))))))
        (setq i (1+ i)))))

  (princ (strcat "\n> " (itoa (length lista-linha))
                 " linha(s) pre-selecionada(s) na faixa de comprimento."))
  (if (= (length lista-linha) 0)
    (progn (princ "\n[AVISO] Nenhuma linha encontrada.") (princ) (exit)))

  ;; ----------------------------------------------------------------
  ;; 2.5 Coleta todas as linhas de aterramento
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 2.5: Buscando linhas de aterramento...")
  (setq ss-ater
    (ssget "X" (list (cons 0 "LWPOLYLINE,LINE")
                     (cons 8 *PEF_LAYER_ATER*)
                     '(410 . "Model"))))
  (setq lista-ater '())
  (if ss-ater
    (progn
      (setq i 0)
      (repeat (sslength ss-ater)
        (setq en (ssname ss-ater i))
        (setq len-val (pef-get-comprimento en))
        (if len-val
          (progn
            (setq centro-val (pef-midpoint en))
            (if centro-val
              (setq lista-ater
                (append lista-ater
                  (list (list (cons "en"     en)
                              (cons "len"    len-val)
                              (cons "centro" centro-val))))))))
        (setq i (1+ i)))))
  (princ (strcat "\n> " (itoa (length lista-ater)) " linha(s) de aterramento encontradas."))

  ;; ----------------------------------------------------------------
  ;; 3. Emparelhamento espacial + identificacao do tipo pelo menor erro
  ;;    combinado (area + comprimento).
  ;;    Angulacao do quadrado e registrada para cada par.
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 3: Emparelhando e identificando tipos...")

  (setq pares '()
        linhas-usadas '())

  (foreach item-quad lista-quad
    (setq en-quad     (cdr (assoc "en"     item-quad))
          area-val    (cdr (assoc "area"   item-quad))
          centro-quad (cdr (assoc "centro" item-quad))
          bbox-quad   (cdr (assoc "bbox"   item-quad))
          ang-quad    (cdr (assoc "ang"    item-quad)))

    (foreach item-linha lista-linha
      (setq en-linha  (cdr (assoc "en"     item-linha))
            len-val   (cdr (assoc "len"    item-linha))
            mid-linha (cdr (assoc "centro" item-linha)))

      (if (and
            (not (member en-linha linhas-usadas))
            mid-linha bbox-quad
            (pef-dentro-bbox? mid-linha (car bbox-quad) (cadr bbox-quad)))
        (progn
          ;; Identifica o tipo com base no erro combinado (area + comprimento)
          (setq tipo-val (pef-identificar-tipo area-val len-val))
          (if (and tipo-val
                   (not (vl-some (lambda (p) (equal (cdr (assoc "quad" p)) en-quad))
                                 pares)))
            (progn
              (setq ater-ents nil)
              (if (member tipo-val '("B" "C"))
                (setq ater-ents (pef-achar-aterramentos centro-quad lista-ater *PEF_TOL_LEN* 25.0)))
              
              ;; So aceita B ou C se encontrar as 4 linhas de aterramento perto
              (if (or (= tipo-val "A") ater-ents)
                (progn
                  (setq linhas-usadas (cons en-linha linhas-usadas))
                  (if ater-ents
                    (foreach ea ater-ents (setq linhas-usadas (cons ea linhas-usadas))))
                  (setq pares
                    (append pares
                      (list (list (cons "quad"   en-quad)
                                  (cons "linha"  en-linha)
                                  (cons "ater"   ater-ents)
                                  (cons "tipo"   tipo-val)
                                  (cons "centro" centro-quad)
                                  (cons "ang"    ang-quad)
                                  (cons "area"   area-val)
                                  (cons "len"    len-val)))))))
            )
          )
        )
      )
    )
  )

  (setq total-pares (length pares))

  (if (= total-pares 0)
    (progn
      (princ "\n[AVISO] Nenhum par encontrado.")
      (princ "\n  Verifique areas/comprimentos com NOPERTO_DIAG.")
      (princ) (exit)))

  (princ (strcat "\n> " (itoa total-pares) " par(es) encontrado(s):"))
  (princ (strcat "\n  FORMADO  (A)    : "
                 (itoa (length (vl-remove-if-not
                                 (lambda (p) (= (cdr (assoc "tipo" p)) "A"))
                                 pares)))))
  (princ (strcat "\n  ATERRADO (B+C)  : "
                 (itoa (length (vl-remove-if-not
                                 (lambda (p) (member (cdr (assoc "tipo" p)) '("B" "C")))
                                 pares)))))

  ;; ----------------------------------------------------------------
  ;; 4. Cria blocos e insere referencias preservando angulacao
  ;;
  ;;    Estrategia de angulacao:
  ;;      - A definicao do bloco e criada a partir do PRIMEIRO par de cada tipo.
  ;;      - Para cada par subsequente, a insercao e rotacionada por:
  ;;          rotacao = ang_atual - ang_referencia
  ;;      - Isso preserva a orientacao original de cada conjunto quadrado+linha.
  ;; ----------------------------------------------------------------
  (princ "\nEtapa 4: Criando blocos com angulacao preservada...")

  (setq n-formado  0
        n-aterrado  0
        bloco-formado-existe  (tblsearch "BLOCK" *PEF_NOME_FORMADO*)
        bloco-aterrado-existe (tblsearch "BLOCK" *PEF_NOME_ATERRADO*)
        ang-ref-formado  (if bloco-formado-existe (pef-get-block-angle *PEF_NOME_FORMADO*) nil)
        ang-ref-aterrado (if bloco-aterrado-existe (pef-get-block-angle *PEF_NOME_ATERRADO*) nil))

  (foreach par pares
    (setq en-quad  (cdr (assoc "quad"   par))
          en-linha (cdr (assoc "linha"  par))
          ater-ents (cdr (assoc "ater"  par))
          tipo-val (cdr (assoc "tipo"   par))
          centro   (cdr (assoc "centro" par))
          ang-quad (cdr (assoc "ang"    par)))

    (setq all-ents (append (list en-quad en-linha) (if ater-ents ater-ents '())))
    (setq todos-existem T)
    (foreach e all-ents
      (if (not (entget e)) (setq todos-existem nil)))

    (if todos-existem
      (progn
        ;; Determina nome do bloco e variaveis de controle
        (setq nome-bloco
          (if (or (= tipo-val "B") (= tipo-val "C")) *PEF_NOME_ATERRADO* *PEF_NOME_FORMADO*))

        (if (or (= tipo-val "B") (= tipo-val "C"))
          (progn
            ;; === ATERRADO (tipos B ou C) ===
            (if (not bloco-aterrado-existe)
              (progn
                ;; Cria definicao a partir deste par (o primeiro)
                (setq bloco-aterrado-existe
                  (pef-criar-bloco-vla nome-bloco centro all-ents))
                (setq ang-ref-aterrado ang-quad)
              )
            )
            (setq rotacao-insert
              (if ang-ref-aterrado (- ang-quad ang-ref-aterrado) 0.0))
            (foreach e all-ents (if (entget e) (entdel e)))
            (pef-inserir-bloco nome-bloco centro rotacao-insert *PEF_LAYER*)
            (setq n-aterrado (1+ n-aterrado))
            (princ (strcat "\n  [ATERRADO " (itoa n-aterrado)
                           "] Tipo " tipo-val "  ang=" (angtos ang-quad 0 2)
                           "  rot=" (angtos rotacao-insert 0 2)
                           "  em (" (rtos (car centro) 2 2)
                           "," (rtos (cadr centro) 2 2) ")."))
          )
          (progn
            ;; === FORMADO (tipo A) ===
            (if (not bloco-formado-existe)
              (progn
                (setq bloco-formado-existe
                  (pef-criar-bloco-vla nome-bloco centro all-ents))
                (setq ang-ref-formado ang-quad)
              )
            )
            (setq rotacao-insert
              (if ang-ref-formado (- ang-quad ang-ref-formado) 0.0))
            (foreach e all-ents (if (entget e) (entdel e)))
            (pef-inserir-bloco nome-bloco centro rotacao-insert *PEF_LAYER*)
            (setq n-formado (1+ n-formado))
            (princ (strcat "\n  [FORMADO " (itoa n-formado)
                           "] Tipo " tipo-val
                           "  ang=" (angtos ang-quad 0 2)
                           "  rot=" (angtos rotacao-insert 0 2)
                           "  em (" (rtos (car centro) 2 2)
                           "," (rtos (cadr centro) 2 2) ")."))
          )
        )
      )
      (princ "\n  [AVISO] Par ignorado: alguma entidade ausente.")
    )
  )

  ;; ----------------------------------------------------------------
  ;; 5. Resumo
  ;; ----------------------------------------------------------------
  (princ "\n====================================================")
  (princ (strcat "\n  CONCLUIDO:"))
  (princ (strcat "\n    " (itoa n-formado)
                 " bloco(s) '" *PEF_NOME_FORMADO* "'"))
  (princ (strcat "\n    " (itoa n-aterrado)
                 " bloco(s) '" *PEF_NOME_ATERRADO* "'"))
  (if (< (+ n-formado n-aterrado) total-pares)
    (princ (strcat "\n  ATENCAO: "
                   (itoa (- total-pares (+ n-formado n-aterrado)))
                   " par(es) nao convertido(s).")))
  (princ "\n====================================================")
  (command "_.REGEN")
  (princ)
)

;;; =========================================================================
;;; POSTEEF_CONFIG
;;; =========================================================================
(defun c:POSTEEF_CONFIG (/ nl naa nla nab nlb nac nlc nta ntl)
  (princ "\n=== POSTEEF CONFIG ===")
  (princ (strcat "\n Layer            : " *PEF_LAYER*))
  (princ (strcat "\n Tipo A (FORMADO)  area=" (rtos *PEF_AREA_A* 2 4)
                 "  len=" (rtos *PEF_LEN_A* 2 4)))
  (princ (strcat "\n Tipo B (ATERRADO) area=" (rtos *PEF_AREA_B* 2 4)
                 "  len=" (rtos *PEF_LEN_B* 2 4)))
  (princ (strcat "\n Tipo C (ATERRADO) area=" (rtos *PEF_AREA_C* 2 4)
                 "  len=" (rtos *PEF_LEN_C* 2 4)))
  (princ (strcat "\n Tol. area: " (rtos *PEF_TOL_AREA* 2 4)
                 "  Tol. len: " (rtos *PEF_TOL_LEN* 2 4)))
  (setq nl (getstring (strcat "\nLayer <" *PEF_LAYER* ">: ")))
  (if (/= (vl-string-trim " " nl) "") (setq *PEF_LAYER* (vl-string-trim " " nl)))
  (setq naa (getreal (strcat "\nArea Tipo A <" (rtos *PEF_AREA_A* 2 4) ">: ")))
  (if naa (setq *PEF_AREA_A* naa))
  (setq nla (getreal (strcat "\nLen  Tipo A <" (rtos *PEF_LEN_A* 2 4) ">: ")))
  (if nla (setq *PEF_LEN_A* nla))
  (setq nab (getreal (strcat "\nArea Tipo B <" (rtos *PEF_AREA_B* 2 4) ">: ")))
  (if nab (setq *PEF_AREA_B* nab))
  (setq nlb (getreal (strcat "\nLen  Tipo B <" (rtos *PEF_LEN_B* 2 4) ">: ")))
  (if nlb (setq *PEF_LEN_B* nlb))
  (setq nac (getreal (strcat "\nArea Tipo C <" (rtos *PEF_AREA_C* 2 4) ">: ")))
  (if nac (setq *PEF_AREA_C* nac))
  (setq nlc (getreal (strcat "\nLen  Tipo C <" (rtos *PEF_LEN_C* 2 4) ">: ")))
  (if nlc (setq *PEF_LEN_C* nlc))
  (setq nta (getreal (strcat "\nTol. area +/- <" (rtos *PEF_TOL_AREA* 2 4) ">: ")))
  (if nta (setq *PEF_TOL_AREA* nta))
  (setq ntl (getreal (strcat "\nTol. len  +/- <" (rtos *PEF_TOL_LEN* 2 4) ">: ")))
  (if ntl (setq *PEF_TOL_LEN* ntl))
  (princ "\n=== Atualizado ===")
  (princ)
)

;;; =========================================================================
;;; POSTEEF_RESET
;;; =========================================================================
(defun c:POSTEEF_RESET ()
  (setq *PEF_LAYER*        "COR_000000"
        *PEF_AREA_A*       17.9521
        *PEF_LEN_A*         4.0265
        *PEF_AREA_B*       17.2936
        *PEF_LEN_B*         3.9918
        *PEF_AREA_C*       17.2805
        *PEF_LEN_C*         3.9953
        *PEF_TOL_AREA*      0.15
        *PEF_TOL_LEN*       0.10
        *PEF_LAYER_ATER*   "COR_994533"
        *PEF_LEN_ATER_1*   1.3051
        *PEF_LEN_ATER_2*   2.0872
        *PEF_LEN_ATER_3*   1.4571
        *PEF_LEN_ATER_4*   1.0432
        *PEF_NOME_FORMADO*  "POSTE_EXISTENTE_FORMADO"
        *PEF_NOME_ATERRADO* "POSTE_EXISTENTE_ATERRADO")
  (princ "\n[POSTEEF_RESET] Parametros resetados.")
  (princ (strcat "\n  Tipo A (FORMADO)  area=" (rtos *PEF_AREA_A* 2 4)
                 "  len=" (rtos *PEF_LEN_A* 2 4)))
  (princ (strcat "\n  Tipo B (ATERRADO) area=" (rtos *PEF_AREA_B* 2 4)
                 "  len=" (rtos *PEF_LEN_B* 2 4)))
  (princ (strcat "\n  Tipo C (ATERRADO) area=" (rtos *PEF_AREA_C* 2 4)
                 "  len=" (rtos *PEF_LEN_C* 2 4)))
  (princ)
)

(princ "\n[NO_PERTO_FORMADO.lsp carregado]")
(princ "\n  --- NO_PERTO_FORMADO ---")
(princ "\n  NOPERTO        - Converte pares poly+hatch em bloco NO_PERTO_FORMADO")
(princ "\n  NOPERTO_DIAG   - Lista areas/layers de todas as polylines e hatches")
(princ "\n  NOPERTO_CONFIG - Altera parametros do NOPERTO")
(princ "\n  NOPERTO_RESET  - Reseta parametros do NOPERTO")
(princ "\n  --- POSTE_EXISTENTE ---")
(princ "\n  POSTEEF        - Cria POSTE_EXISTENTE_FORMADO e POSTE_EXISTENTE_ATERRADO")
(princ "\n  POSTEEF_CONFIG - Altera parametros do POSTEEF")
(princ "\n  POSTEEF_RESET  - Reseta parametros do POSTEEF")
(princ)

;;; =========================================================================
;;; PARAMETROS GLOBAIS - PRMT_FORMADO E TRAFO_EXISTENTE_FORMADO
;;; =========================================================================
(setq *PRMT_LAYER*       "COR_000000")
(setq *PRMT_LEN_1*       5.6574)
(setq *PRMT_LEN_2*       7.4428)
(setq *PRMT_LEN_3*       4.6108)
(setq *PRMT_LEN_4*       7.4466)
(setq *PRMT_LEN_5*       4.6143)
(setq *PRMT_TOL_LEN*     0.30)
(setq *PRMT_TOL_DIST*    30.0)
(setq *PRMT_NOME_BLOCO*  "PRMT_FORMADO")

(setq *TRAFO_LAYER*      "COR_000000")
(setq *TRAFO_AREA*       16.3433)
(setq *TRAFO_LEN*        4.2512)
(setq *TRAFO_TOL_AREA*   0.15)
(setq *TRAFO_TOL_LEN*    0.10)
(setq *TRAFO_NOME_BLOCO* "TRAFO_EXISTENTE_FORMADO")

;;; =========================================================================
;;; RUN_PRMT_FORMADO
;;; =========================================================================
(defun run-prmt-formado (/ ss i en len-val c-val lista-linhas
                           cand-1 cand-2 cand-3 cand-4 cand-5
                           grupos linhas-usadas c1 e1
                           res l e e2 e3 e4 e5 all-ents
                           centro-grupo pt-base ang-base
                           bloco-existe err n-prmt doc blocos blk-def arr pt3d obj)
  (princ "\n====================================================")
  (princ "\n  PRMT_FORMADO - Identificacao e criacao do bloco")
  (princ "\n====================================================")
  (setq ss (ssget "X" (list '(0 . "LWPOLYLINE,LINE") (cons 8 *PRMT_LAYER*) '(410 . "Model"))))
  (setq lista-linhas '())
  (if ss
    (progn
      (setq i 0)
      (repeat (sslength ss)
        (setq en (ssname ss i))
        (setq len-val (pef-get-comprimento en))
        (if len-val
          (progn
            (setq c-val (pef-midpoint en))
            (if c-val
              (setq lista-linhas (append lista-linhas (list (list (cons "en" en) (cons "len" len-val) (cons "c" c-val))))))))
        (setq i (1+ i)))))
        
  (setq cand-1 '() cand-2 '() cand-3 '() cand-4 '() cand-5 '())
  (foreach item lista-linhas
    (setq l (cdr (assoc "len" item)))
    (cond
      ((<= (abs (- l *PRMT_LEN_1*)) *PRMT_TOL_LEN*) (setq cand-1 (cons item cand-1)))
      ((<= (abs (- l *PRMT_LEN_2*)) *PRMT_TOL_LEN*) (setq cand-2 (cons item cand-2)))
      ((<= (abs (- l *PRMT_LEN_3*)) *PRMT_TOL_LEN*) (setq cand-3 (cons item cand-3)))
      ((<= (abs (- l *PRMT_LEN_4*)) *PRMT_TOL_LEN*) (setq cand-4 (cons item cand-4)))
      ((<= (abs (- l *PRMT_LEN_5*)) *PRMT_TOL_LEN*) (setq cand-5 (cons item cand-5)))
    )
  )
  
  (setq grupos '() linhas-usadas '())
  ;; Iterar sobre a linha base (5.6574)
  (foreach c1 cand-1
    (setq e1 (cdr (assoc "en" c1)))
    (if (not (member e1 linhas-usadas))
      (progn
        (setq centro-grupo (cdr (assoc "c" c1)))
        ;; Achar as outras 4 pertinho
        (setq e2 nil e3 nil e4 nil e5 nil)
        (foreach c2 cand-2
          (if (and (not e2) (not (member (cdr (assoc "en" c2)) linhas-usadas))
                   (<= (distance centro-grupo (cdr (assoc "c" c2))) *PRMT_TOL_DIST*))
            (setq e2 (cdr (assoc "en" c2)))))
        (foreach c3 cand-3
          (if (and (not e3) (not (member (cdr (assoc "en" c3)) linhas-usadas))
                   (<= (distance centro-grupo (cdr (assoc "c" c3))) *PRMT_TOL_DIST*))
            (setq e3 (cdr (assoc "en" c3)))))
        (foreach c4 cand-4
          (if (and (not e4) (not (member (cdr (assoc "en" c4)) linhas-usadas))
                   (<= (distance centro-grupo (cdr (assoc "c" c4))) *PRMT_TOL_DIST*))
            (setq e4 (cdr (assoc "en" c4)))))
        (foreach c5 cand-5
          (if (and (not e5) (not (member (cdr (assoc "en" c5)) linhas-usadas))
                   (<= (distance centro-grupo (cdr (assoc "c" c5))) *PRMT_TOL_DIST*))
            (setq e5 (cdr (assoc "en" c5)))))
            
        (if (and e1 e2 e3 e4 e5)
          (progn
            (setq grupos (append grupos (list (list e1 e2 e3 e4 e5 centro-grupo (pef-get-angulo e1)))))
            (setq linhas-usadas (append linhas-usadas (list e1 e2 e3 e4 e5)))
          )
        )
      )
    )
  )
  
  (princ (strcat "\n> " (itoa (length grupos)) " grupo(s) PRMT encontrado(s)."))
  (setq n-prmt 0 bloco-existe (tblsearch "BLOCK" *PRMT_NOME_BLOCO*))
  (setq ang-base (if bloco-existe (pef-get-block-angle *PRMT_NOME_BLOCO*) nil))
  
  (foreach grp grupos
    (setq all-ents (list (nth 0 grp) (nth 1 grp) (nth 2 grp) (nth 3 grp) (nth 4 grp))
          centro-grupo (nth 5 grp)
          ang-atual (nth 6 grp))
    (setq todos-existem T)
    (foreach e all-ents (if (not (entget e)) (setq todos-existem nil)))
    
    (if todos-existem
      (progn
        (if (not bloco-existe)
          (progn
            (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)) blocos (vla-get-Blocks doc))
            (setq pt3d (vlax-3d-point (car centro-grupo) (cadr centro-grupo) 0.0))
            (setq err (vl-catch-all-apply (lambda () (setq blk-def (vla-Add blocos pt3d *PRMT_NOME_BLOCO*))) nil))
            (if (not (vl-catch-all-error-p err))
              (progn
                (setq arr (vlax-make-safearray vlax-vbObject '(0 . 4)))
                (setq i 0)
                (foreach en all-ents
                  (setq obj (vlax-ename->vla-object en))
                  (vlax-safearray-put-element arr i obj)
                  (setq i (1+ i)))
                (vl-catch-all-apply (lambda () (vla-CopyObjects doc arr blk-def)) nil)
                (setq bloco-existe T ang-base ang-atual)
                (princ (strcat "\n> Bloco '" *PRMT_NOME_BLOCO* "' criado."))))
          )
        )
        
        (setq rotacao (if ang-base (- ang-atual ang-base) 0.0))
        (foreach e all-ents (if (entget e) (entdel e)))
        (pef-inserir-bloco *PRMT_NOME_BLOCO* centro-grupo rotacao *PRMT_LAYER*)
        (setq n-prmt (1+ n-prmt))
        (princ (strcat "\n  [PRMT " (itoa n-prmt) "] Inserido em (" (rtos (car centro-grupo) 2 2) "," (rtos (cadr centro-grupo) 2 2) ")."))
      )
    )
  )
  (princ "\n")
)

;;; =========================================================================
;;; RUN_TRAFO_EXISTENTE
;;; =========================================================================
(defun run-trafo-existente (/ ss-quad ss-hatch ss-linha
                              lista-quad lista-hatch lista-linha
                              i en a-val c-val l-val bbox-val ang-val
                              pares par hatch-usados linhas-usadas
                              c-quad e-quad e-hatch e-linha
                              dist melhor-hatch melhor-dist
                              n-trafo bloco-existe ang-base all-ents
                              doc blocos pt3d blk-def arr obj err)
  (princ "\n====================================================")
  (princ "\n  TRAFO_EXISTENTE - Identificacao e criacao do bloco")
  (princ "\n====================================================")
  
  ;; Polylines
  (setq ss-quad (ssget "X" (list '(0 . "LWPOLYLINE") (cons 8 *TRAFO_LAYER*) '(410 . "Model"))))
  (setq lista-quad '())
  (if ss-quad
    (progn (setq i 0)
      (repeat (sslength ss-quad)
        (setq en (ssname ss-quad i) a-val (npf-get-area en))
        (if (and a-val (>= a-val (- *TRAFO_AREA* *TRAFO_TOL_AREA*)) (<= a-val (+ *TRAFO_AREA* *TRAFO_TOL_AREA*)))
          (progn
            (setq c-val (npf-centro-entidade en) bbox-val (pef-get-bbox en) ang-val (pef-get-angulo en))
            (if (and c-val bbox-val)
              (setq lista-quad (append lista-quad (list (list (cons "en" en) (cons "c" c-val) (cons "bbox" bbox-val) (cons "ang" ang-val))))))))
        (setq i (1+ i)))))
        
  ;; Hatches
  (setq ss-hatch (ssget "X" (list '(0 . "HATCH") (cons 8 *TRAFO_LAYER*) '(410 . "Model"))))
  (setq lista-hatch '())
  (if ss-hatch
    (progn (setq i 0)
      (repeat (sslength ss-hatch)
        (setq en (ssname ss-hatch i) a-val (npf-get-area en))
        (if (and a-val (>= a-val (- *TRAFO_AREA* *TRAFO_TOL_AREA*)) (<= a-val (+ *TRAFO_AREA* *TRAFO_TOL_AREA*)))
          (progn
            (setq c-val (npf-centro-entidade en))
            (if c-val (setq lista-hatch (append lista-hatch (list (list (cons "en" en) (cons "c" c-val))))))))
        (setq i (1+ i)))))

  ;; Linhas
  (setq ss-linha (ssget "X" (list '(0 . "LWPOLYLINE,LINE") (cons 8 *TRAFO_LAYER*) '(410 . "Model"))))
  (setq lista-linha '())
  (if ss-linha
    (progn (setq i 0)
      (repeat (sslength ss-linha)
        (setq en (ssname ss-linha i) l-val (pef-get-comprimento en))
        (if (and l-val (>= l-val (- *TRAFO_LEN* *TRAFO_TOL_LEN*)) (<= l-val (+ *TRAFO_LEN* *TRAFO_TOL_LEN*)))
          (progn
            (setq c-val (pef-midpoint en))
            (if c-val (setq lista-linha (append lista-linha (list (list (cons "en" en) (cons "c" c-val))))))))
        (setq i (1+ i)))))

  (setq pares '() hatch-usados '() linhas-usadas '())
  (foreach q lista-quad
    (setq e-quad (cdr (assoc "en" q)) c-quad (cdr (assoc "c" q)) bbox-quad (cdr (assoc "bbox" q)) ang-quad (cdr (assoc "ang" q)))
    (setq melhor-hatch nil melhor-dist 99999.0)
    (foreach h lista-hatch
      (if (not (member (cdr (assoc "en" h)) hatch-usados))
        (progn
          (setq dist (distance c-quad (cdr (assoc "c" h))))
          (if (< dist melhor-dist) (setq melhor-dist dist melhor-hatch (cdr (assoc "en" h)))))))
    
    (if (and melhor-hatch (<= melhor-dist 5.0))
      (progn
        (setq e-linha nil)
        (foreach l lista-linha
          (if (and (not e-linha) (not (member (cdr (assoc "en" l)) linhas-usadas))
                   (<= (distance c-quad (cdr (assoc "c" l))) 15.0))
            (setq e-linha (cdr (assoc "en" l)))))
            
        (if e-linha
          (progn
            (setq pares (append pares (list (list e-quad melhor-hatch e-linha c-quad ang-quad))))
            (setq hatch-usados (cons melhor-hatch hatch-usados))
            (setq linhas-usadas (cons e-linha linhas-usadas))
          )
        )
      )
    )
  )

  (princ (strcat "\n> " (itoa (length pares)) " grupo(s) TRAFO encontrado(s)."))
  (setq n-trafo 0 bloco-existe (tblsearch "BLOCK" *TRAFO_NOME_BLOCO*))
  (setq ang-base (if bloco-existe (pef-get-block-angle *TRAFO_NOME_BLOCO*) nil))
  
  (foreach par pares
    (setq all-ents (list (nth 0 par) (nth 1 par) (nth 2 par))
          c-quad (nth 3 par) ang-atual (nth 4 par))
    (setq todos-existem T)
    (foreach e all-ents (if (not (entget e)) (setq todos-existem nil)))
    
    (if todos-existem
      (progn
        (if (not bloco-existe)
          (progn
            (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)) blocos (vla-get-Blocks doc))
            (setq pt3d (vlax-3d-point (car c-quad) (cadr c-quad) 0.0))
            (setq err (vl-catch-all-apply (lambda () (setq blk-def (vla-Add blocos pt3d *TRAFO_NOME_BLOCO*))) nil))
            (if (not (vl-catch-all-error-p err))
              (progn
                (setq arr (vlax-make-safearray vlax-vbObject '(0 . 2)))
                (setq i 0)
                (foreach en all-ents
                  (setq obj (vlax-ename->vla-object en))
                  (vlax-safearray-put-element arr i obj)
                  (setq i (1+ i)))
                (vl-catch-all-apply (lambda () (vla-CopyObjects doc arr blk-def)) nil)
                (setq bloco-existe T ang-base ang-atual)
                (princ (strcat "\n> Bloco '" *TRAFO_NOME_BLOCO* "' criado."))))
          )
        )
        
        (setq rotacao (if ang-base (- ang-atual ang-base) 0.0))
        (foreach e all-ents (if (entget e) (entdel e)))
        (pef-inserir-bloco *TRAFO_NOME_BLOCO* c-quad rotacao *TRAFO_LAYER*)
        (setq n-trafo (1+ n-trafo))
        (princ (strcat "\n  [TRAFO " (itoa n-trafo) "] Inserido em (" (rtos (car c-quad) 2 2) "," (rtos (cadr c-quad) 2 2) ")."))
      )
    )
  )
  (princ "\n")
)

;;; =========================================================================
;;; COMANDO UNIFICADO NOPERTO
;;; =========================================================================
(defun c:NOPERTO ()
  (vl-load-com)
  (princ "\n====================================================")
  (princ "\n  INICIANDO BATCH DE CONVERSAO DE BLOCOS")
  (princ "\n====================================================")
  
  (run-no-perto-formado)
  (run-poste-existente)
  (run-prmt-formado)
  (run-trafo-existente)
  
  (princ "\n====================================================")
  (princ "\n  BATCH CONCLUIDO COM SUCESSO")
  (princ "\n====================================================")
  (princ)
)
