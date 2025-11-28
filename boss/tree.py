class TreeNode:
    def __init__(self, val=None, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

    def mid_travelsal(self, root):
        """
        中序遍历
        左子树->根节点->右子树
        :param root:
        :return:
        """
        if root.left:
            self.mid_travelsal(root.left)
        print(root.val)
        if root.right:
            self.mid_travelsal(root.right)

    def pre_travelsal(self, root):
        """
        前序遍历
        根节点->左子树->右子树
        :param root:
        :return:
        """
        print(root.val)
        if root.left:
            self.pre_travelsal(root.left)
        if root.right:
            self.pre_travelsal(root.right)

    def post_travelsal(self, root):
        """
        后序遍历
        左子树->右子树->根节点
        :param root:
        :return:
        """
        if root.left:
            self.post_travelsal(root.left)
        if root.right:
            self.post_travelsal(root.right)
        print(root.val)

    def max_depth(self, root):
        """
        二叉树的最大深度
        :param root:
        :return:
        """
        if root is None:
            return 0
        left_depth = self.max_depth(root.left)
        right_depth = self.max_depth(root.right)
        return max(left_depth, right_depth) + 1

    def is_same_tree(self, p, q):
        """
        相同的树
        :param p:
        :param q:
        :return:
        """
        if p is None and q is None:
            return True
        if p is None or q is None:
            return False
        return p.val == q.val and self.is_same_tree(p.left, q.left) and self.is_same_tree(p.right, q.right)

    def is_subtree(self, root, subRoot):
        """
        另一棵树的子树
        :param root:
        :param subRoot:
        :return:
        """
        if root is None:
            return False
        if self.is_same_tree(root, subRoot):
            return True
        return self.is_subtree(root.left, subRoot) or self.is_subtree(root.right, subRoot)
    
