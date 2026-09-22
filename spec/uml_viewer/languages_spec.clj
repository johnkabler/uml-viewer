(ns uml-viewer.languages-spec
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [speclj.core :refer :all]
            [uml-viewer.application.detail :as detail]
            [uml-viewer.application.document :as document]
            [uml-viewer.application.events :as events]
            [uml-viewer.application.ir-generator :as ir-generator]
            [uml-viewer.application.metrics :as metrics]
            [uml-viewer.application.overlay :as overlay]
            [uml-viewer.engine.layout :as layout]
            [uml-viewer.graph :as graph]
            [uml-viewer.languages.external :as external]
            [uml-viewer.main.discover :as discover]
            [uml-viewer.source :as source]))

(def py-src "spec/fixtures/python_app/src")
(def ts-src "spec/fixtures/ts_app/src")

(defn- by-id [graph]
  (into {} (map (juxt :id identity) (:classes graph))))

(defn- edge-set [graph]
  (set (map (juxt :from :to :kind) (:edges graph))))

(defn- member [graph ns-name name]
  (first (filter #(and (= ns-name (:ns %)) (= name (:name %))) (:members graph))))

(defn- py-policy []
  {:title "Python app"
   :src py-src
   :prefix "myapp"
   :lang :python
   :hierarchical true
   :order [:domain :app]
   :levels [[:domain] [:app]]})

(defn- ts-policy []
  {:title "TS app"
   :src ts-src
   :prefix ""
   :lang :typescript
   :hierarchical true
   :order [:domain :app]
   :levels [[:domain] [:app]]})

(defn- spit-policy [dir policy]
  (let [f (io/file dir "policy.edn")]
    (.mkdirs dir)
    (spit f (pr-str policy))
    (.getPath f)))

(describe "CRAP formula"
  (it "is CC squared times uncovered cubed, plus CC"
    (should= 1.0 (metrics/crap-score 1 100))
    (should= 2.0 (metrics/crap-score 1 0))))

(describe "python scanner"
  (it "maps modules, imports, protocols, and privacy"
    (let [g (graph/scan external/python-graph py-src {:prefix "myapp"})
          classes (by-id g)
          edges (edge-set g)
          ids (set (keys classes))]
      (should (contains? ids :domain.repo))
      (should (contains? ids :domain.models))
      (should (contains? ids :app.loan))
      (should (contains? ids :app.cli))
      (should-not (contains? ids :app.loan_test))
      (should= :interface (:stereotype (classes :domain.repo)))
      (should-be-nil (:stereotype (classes :domain.models)))
      (should (contains? edges [:app.loan :domain.repo :implements]))
      (should (contains? edges [:app.loan :domain.models :dependency]))
      (should (contains? edges [:app.cli :domain.models :dependency]))
      (should (contains? edges [:app.cli :app.loan :dependency]))
      (should (contains? edges [:app.cli :domain.repo :dependency]))
      (should (contains? edges [:domain.models :app.loan :dependency]))
      (should (:private (member g "myapp.app.loan" "_audit")))
      (should-not (:private (member g "myapp.app.loan" "issue")))
      (should= 1 (:complexity (member g "myapp.app.loan" "issue")))
      (should= 2 (:complexity (member g "myapp.app.loan" "LoanRepo.get")))
      (should= 2 (:complexity (member g "myapp.domain.models" "title_of")))))

  (it "opens a function at its line"
    (let [found (source/member-source {:lang :python
                                       :src py-src
                                       :prefix "myapp"
                                       :ns "myapp.app.loan"
                                       :name "issue"})]
      (should (str/ends-with? (:file found) "loan.py"))
      (should (str/includes? (nth (str/split-lines (:body found)) (dec (:line found)))
                             "def issue"))))

  (it "marks the inward-breaking import and lists members on the card"
    (let [root (io/file "target" "py-uml-view")
          policy (spit-policy root (py-policy))
          edn (io/file root "app.edn")
          _ (ir-generator/generate external/python-graph policy (.getPath edn)
                                   {:metrics-root (.getPath root)})
          state (document/load-path (.getPath edn))
          doc (:doc state)
          bad (first (filter #(and (= :domain.models (:from %))
                                   (= :app.loan (:to %)))
                             (:edges doc)))
          model (detail/model (events/card-scene state) :app.loan)
          lines (map :text (layout/class-lines (:class model)))]
      (should= :python (:lang doc))
      (should= py-src (:src doc))
      (should-not (some #(= :os (:id %)) (:classes doc)))
      (should (:violating bad))
      (should (some #{"issue"} lines))
      (should-not (some #{"_audit"} lines))
      (should (str/includes? (:body (source/member-source
                                      {:lang :python :src (:src doc) :prefix "myapp"
                                       :ns "myapp.app.loan" :name "issue"}))
                             "def issue")))))

(describe "typescript scanner"
  (it "maps files, path aliases, import type, and stereotypes"
    (let [g (graph/scan external/typescript-graph ts-src {:prefix ""})
          classes (by-id g)
          edges (edge-set g)
          ids (set (keys classes))]
      (should (contains? ids :domain.book))
      (should (contains? ids :domain.repo))
      (should (contains? ids :domain.status))
      (should (contains? ids :domain.service))
      (should (contains? ids :domain.bad))
      (should (contains? ids :app.loan))
      (should (contains? ids :app))
      (should-not (contains? ids :app.loan.test))
      (should= :interface (:stereotype (classes :domain.book)))
      (should= :enumeration (:stereotype (classes :domain.status)))
      (should= :abstract (:stereotype (classes :domain.service)))
      (should (contains? edges [:domain.repo :domain.book :dependency]))
      (should (contains? edges [:app.loan :domain.book :dependency]))
      (should (contains? edges [:app.loan :domain.repo :implements]))
      (should (contains? edges [:app.loan :domain.service :inheritance]))
      (should (contains? edges [:domain.bad :app.loan :dependency]))
      (should (contains? edges [:app :app.loan :dependency]))
      (should (:private (member g "app.loan" "_audit")))
      (should-not (:private (member g "app.loan" "issue")))
      (should= 2 (:complexity (member g "app.loan" "issue")))))

  (it "opens a function at its line"
    (let [found (source/member-source {:lang :typescript
                                       :src ts-src
                                       :prefix ""
                                       :ns "app.loan"
                                       :name "issue"})]
      (should (str/ends-with? (:file found) "loan.ts"))
      (should (str/includes? (nth (str/split-lines (:body found)) (dec (:line found)))
                             "function issue"))))

  (it "marks the dependency-rule break on the loaded diagram"
    (let [root (io/file "target" "ts-uml-view")
          policy (spit-policy root (ts-policy))
          edn (io/file root "app.edn")
          _ (ir-generator/generate external/typescript-graph policy (.getPath edn)
                                   {:metrics-root (.getPath root)})
          state (document/load-path (.getPath edn))
          doc (:doc state)
          bad (first (filter #(and (= :domain.bad (:from %))
                                   (= :app.loan (:to %)))
                             (:edges doc)))
          model (detail/model (events/card-scene state) :app.loan)
          lines (map :text (layout/class-lines (:class model)))]
      (should= :typescript (:lang doc))
      (should (:violating bad))
      (should (some #{"issue"} lines))
      (should-not (some #{"_audit"} lines)))))

(describe "coverage and mutation import"
  (it "keeps coverage across a rescan and computes CRAP"
    (let [root (io/file "target" "py-coverage")
          g (graph/scan external/python-graph py-src {:prefix "myapp"})
          issue (member g "myapp.app.loan" "issue")
          cov-file (io/file root "coverage.json")]
      (.mkdirs root)
      (spit cov-file
            (str "{\"files\":{\"" (:file issue) "\":{"
                 "\"executed_lines\":[" (:line issue) "],"
                 "\"missing_lines\":[]}}}"))
      (metrics/import-coverage! (.getPath root)
                                {:lang :python :src py-src :prefix "myapp"}
                                (.getPath cov-file))
      (metrics/write-static! (.getPath root) (:members g))
      (let [entries (:entries (edn/read-string (slurp (io/file root ".metrics" "crap.edn"))))
            row (first (filter #(and (= "myapp.app.loan" (:namespace %))
                                     (= "issue" (:name %)))
                               entries))]
        (should= 100.0 (:coverage row))
        (should= 1.0 (:crap row)))))

  (it "imports a normalized mutmut report and a Stryker report"
    (let [root (io/file "target" "mut-import")
          py (io/file root "mut.json")
          ts-report (io/file root "stryker.json")
          g (graph/scan external/typescript-graph ts-src {:prefix ""})
          issue (member g "app.loan" "issue")]
      (.mkdirs root)
      (spit py (str "{\"modules\":[{\"namespace\":\"myapp.app.loan\","
                    "\"source\":\"loan.py\",\"forms\":[{\"name\":\"issue\","
                    "\"private\":false,\"killed\":2,\"survived\":1,\"uncovered\":0}]}]}"))
      (metrics/import-mutation! (.getPath root)
                                {:lang :python :src py-src :prefix "myapp"}
                                (.getPath py))
      (spit ts-report
            (str "{\"files\":{\"" (:file issue) "\":{\"mutants\":["
                 "{\"status\":\"Killed\",\"location\":{\"start\":{\"line\":" (:line issue) "}}},"
                 "{\"status\":\"Survived\",\"location\":{\"start\":{\"line\":" (:line issue) "}}},"
                 "{\"status\":\"NoCoverage\",\"location\":{\"start\":{\"line\":" (:line issue) "}}}"
                 "]}}}"))
      (metrics/import-mutation! (.getPath root)
                                {:lang :typescript :src ts-src :prefix ""}
                                (.getPath ts-report))
      (let [py-snap (edn/read-string
                      (slurp (io/file root ".metrics" "mutate" "myapp" "app" "loan.edn")))
            ts-snap (edn/read-string
                      (slurp (io/file root ".metrics" "mutate" "app" "loan.edn")))
            py-form (first (:forms py-snap))
            ts-form (first (filter #(= "issue" (:name %)) (:forms ts-snap)))]
        (should= 2 (:killed py-form))
        (should= 1 (:survived py-form))
        (should= 3 (:sites py-form))
        (should= 1 (:killed ts-form))
        (should= 1 (:survived ts-form))
        (should= 1 (:uncovered ts-form))))))

(describe "discover"
  (it "writes a hierarchical policy and agent notes without inventing levels"
    (let [out (io/file "target" "discovered-policy.edn")
          notes (io/file "spec/fixtures/python_app/.uml-viewer")
          grok-rule (io/file "spec/fixtures/python_app/.grok")]
      (try
        (discover/discover! "spec/fixtures/python_app" (.getPath out))
        (let [policy (edn/read-string (slurp out))
              agent (slurp (io/file notes "AGENT.md"))
              rule (slurp (io/file grok-rule "rules" "uml-viewer.md"))]
          (should= :python (:lang policy))
          (should= "myapp" (:prefix policy))
          (should= "src" (:src policy))
          (should (:hierarchical policy))
          (should (contains? (set (:order policy)) :domain))
          (should (contains? (set (:order policy)) :app))
          (should-not (contains? policy :levels))
          (should-not (contains? policy :proposals))
          (should (str/includes? agent "to-agent.edn"))
          (should (str/includes? agent ":refresh-crap"))
          (should (str/includes? rule "to-agent.edn")))
        (finally
          (io/delete-file out true)
          (doseq [dir [notes grok-rule]
                  f (reverse (file-seq dir))]
            (io/delete-file f true)))))))
