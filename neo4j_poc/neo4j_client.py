from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri='bolt://localhost:7687', username='neo4j', password='password'):
        """
        初始化 Neo4j 连接
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        """
        关闭连接
        """
        self.driver.close()

    def clear_database(self):
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))

    # ---------------- 节点操作 ----------------
    def create_node(self, label, properties):
        """
        创建单个节点，使用 MERGE 避免重复
        """
        with self.driver.session() as session:
            session.execute_write(self._create_node_tx, label, properties)

    @staticmethod
    def _create_node_tx(tx, label, properties):
        props_str = ', '.join([f"{k}: ${k}" for k in properties.keys()])
        cypher = f"MERGE (n:{label} {{ {props_str} }})"
        tx.run(cypher, **properties)

    def create_nodes_batch(self, label, list_of_properties):
        """
        批量创建节点
        """
        for props in list_of_properties:
            self.create_node(label, props)

    # ---------------- 关系操作 ----------------
    def create_relationship(self, from_label, from_key, from_value,
                            to_label, to_key, to_value, rel_type):
        """
        创建关系，使用 MERGE 避免重复
        """
        with self.driver.session() as session:
            session.execute_write(
                self._create_relationship_tx,
                from_label, from_key, from_value,
                to_label, to_key, to_value,
                rel_type
            )

    @staticmethod
    def _create_relationship_tx(tx, from_label, from_key, from_value,
                                to_label, to_key, to_value, rel_type):
        cypher = f"""
        MATCH (a:{from_label} {{{from_key}: $from_value}})
        MATCH (b:{to_label} {{{to_key}: $to_value}})
        MERGE (a)-[r:{rel_type}]->(b)
        """
        tx.run(cypher, from_value=from_value, to_value=to_value)

    # ---------------- 查询操作 ----------------
    def query(self, cypher, **params):
        """
        执行查询语句
        """
        with self.driver.session() as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher, **params)))
            return [record.data() for record in result]

    # ---------------- 清理重复节点 ----------------
    def delete_duplicate_nodes(self, label, unique_key):
        """
        删除重复节点，只保留每个 unique_key 的一个节点
        """
        cypher = f"""
        MATCH (n:{label})
        WITH n.{unique_key} AS key, COLLECT(n) AS nodes
        WHERE SIZE(nodes) > 1
        FOREACH (node IN TAIL(nodes) | DETACH DELETE node)
        """
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher))


# ----------------- 使用示例 -----------------
if __name__ == "__main__":
    client = Neo4jClient(uri='bolt://172.16.11.24:7687', username='neo4j', password='password')

    # client.clear_database()
    # client.close()
    # print("数据库已清空")


    # # 创建单个节点
    # client.create_node("Person", {"name": "Alice", "age": 30})
    # client.create_node("Person", {"name": "Bob", "age": 28})
    #
    # # 批量创建节点
    # people = [{"name": "Tom", "age": 65}, {"name": "Jerry", "age": 60}]
    # client.create_nodes_batch("Person", people)
    #
    # # 创建关系
    # client.create_relationship(
    #     "Person", "name", "Alice",
    #     "Person", "name", "Bob",
    #     "FRIENDS_WITH"
    # )
    #
    # # 查询节点
    # records = client.query("MATCH (p:Person) RETURN p.name AS name, p.age AS age")
    # for r in records:
    #     print(f"{r['name']} - {r['age']}")
    #
    # client.close()