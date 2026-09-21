(ns uml-viewer.main.ir-generator
  (:require [clojure.java.io :as io]
            [uml-viewer.clojure-language.graph-clojure]
            [uml-viewer.languages.external]
            [uml-viewer.application.ir-generator :as ir-generator])
  (:gen-class))

(defn- default-policy
  "This repo keeps its policy under examples/. A discovered project writes
   uml-viewer.policy.edn in the directory you ran ./uml from."
  []
  (let [example "examples/uml-viewer.policy.edn"
        plain "uml-viewer.policy.edn"]
    (cond
      (.isFile (io/file example)) example
      (.isFile (io/file plain)) plain
      :else example)))

(defn -main [& args]
  (let [policy (or (first args) (default-policy))
        out (second args)]
    (println "Wrote" (ir-generator/generate-from-policy policy out))))
