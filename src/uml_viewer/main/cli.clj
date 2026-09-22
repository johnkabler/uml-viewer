(ns uml-viewer.main.cli
  "Project command: discover the tree, write the diagram, open the window."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [uml-viewer.adapters.core :as core]
            [uml-viewer.application.ir-generator :as ir-generator]
            [uml-viewer.clojure-language.graph-clojure]
            [uml-viewer.clojure-language.source-clojure]
            [uml-viewer.languages.external :as external]
            [uml-viewer.main.discover :as discover]
            [uml-viewer.main.metrics :as metrics])
  (:gen-class))

(defn- project-root []
  (io/file (System/getProperty "user.dir")))

(defn- policy-file []
  (let [example (io/file (project-root) "examples" "uml-viewer.policy.edn")
        plain (io/file (project-root) "uml-viewer.policy.edn")]
    (cond
      (.isFile example) example
      (.isFile plain) plain
      :else plain)))

(defn- tool-repo?
  "This checkout keeps its own policy under examples/ and should not gain
   a second gitignore block for a project-level diagram."
  []
  (.isFile (io/file (project-root) "examples" "uml-viewer.policy.edn")))

(defn- ensure-gitignore! []
  (when-not (tool-repo?)
    (let [file (io/file (project-root) ".gitignore")
          begin "# BEGIN UML-VIEWER"
          end "# END UML-VIEWER"
          lines (if (.isFile file) (str/split-lines (slurp file)) [])
          kept (loop [xs lines acc [] inside false]
                 (if (seq xs)
                   (let [line (first xs)]
                     (cond
                       (= line begin) (recur (rest xs) acc true)
                       (= line end) (recur (rest xs) acc false)
                       inside (recur (rest xs) acc inside)
                       :else (recur (rest xs) (conj acc line) false)))
                   acc))
          block [begin ".uml-viewer/" ".metrics/" "/uml-viewer.edn" end]
          body (vec kept)
          body (if (or (empty? body) (str/blank? (peek body))) body (conj body ""))]
      (spit file (str (str/join "\n" (concat body block)) "\n")))))

(defn- lang-of [file]
  (when (.isFile file)
    (keyword (:lang (edn/read-string (slurp file))))))

(defn prepare!
  "Policy path for this directory. Python and TypeScript trees are
   re-discovered so new directories show up. :levels already in the
   policy are kept. A Clojure policy is left as written."
  []
  (let [file (policy-file)
        lang (lang-of file)]
    (ensure-gitignore!)
    (if (= :clojure lang)
      (.getPath file)
      (do
        (when-not (or lang (external/probe-lang (project-root)))
          (throw (ex-info "No Python, TypeScript, or Clojure project found here."
                          {:cwd (.getPath (project-root))})))
        (discover/discover! (project-root) (.getPath file))))))

(defn generate! []
  (let [out (ir-generator/generate-from-policy (prepare!))]
    (println "Wrote" out)
    out))

(defn open! [path]
  (core/start! (external/dispatch-source) "--show" path))

(defn usage []
  (println "usage: uml [command]")
  (println)
  (println "  (no args)       scan this project, write the diagram, open the window")
  (println "  refresh         scan and write the diagram, leave the window alone")
  (println "  show [file]     open a diagram that already exists")
  (println "  coverage FILE   import a coverage.py or Istanbul JSON report")
  (println "  mutate FILE     import a mutmut, Stryker, or normalized mutation report")
  (println "  help")
  (println)
  (println "bin/uml install links the command and a Grok skill."))

(defn -main [& args]
  (let [[cmd & more] args]
    (case cmd
      (nil "open" "up") (open! (generate!))
      "refresh" (generate!)
      "show" (open! (or (first more) "uml-viewer.edn"))
      ("coverage" "mutate") (apply metrics/-main cmd more)
      ("help" "-h" "--help") (usage)
      (do (println "unknown command:" cmd)
          (usage)
          (System/exit 2)))))
